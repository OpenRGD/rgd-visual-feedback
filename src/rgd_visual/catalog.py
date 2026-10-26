"""VISUAL-0.2C — operator-controlled, local, append-only-by-protocol catalog.

This is deliberately NOT part of the BLE daemon, Voice Studio, Console or
Cognitive ingress. Local import/approval/rollback can never command hardware.

Storage integrity: snapshots are individually validated and hash-chained, but
they are NOT digitally signed, canonical Chronons, immutable to their owning
Unix user, or independent proof of operator identity.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Iterator
import uuid

from .expressions import validate_expression, validate_proposal

ROBOT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
EXPR_ID = re.compile(r"^[a-z][a-z0-9_]{2,47}$")
HEX_ID = re.compile(r"^[a-f0-9]{32}$")
REVISION_FILE = re.compile(r"^rev-([0-9]{6})\.json$")
DEFAULT_ROOT = Path.home() / ".local/share/openrgd/visual-feedback/catalogs"
PENDING_SCHEMA = "openrgd.visual.catalog-proposal.v0.1-candidate"
HISTORY_SCHEMA = "openrgd.visual.catalog-revision.v0.1-candidate"
REJECTION_SCHEMA = "openrgd.visual.catalog-rejection.v0.1-candidate"
MAX_FILE_BYTES = 32 * 1024
MAX_CATALOG_ENTRIES = 256   # Independent from Studio's 32 active scene recipes.
MAX_REVISIONS_PER_ID = 512
MAX_PROPOSALS = 4096


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _exact(value: Any, fields: set[str], description: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"Invalid {description} fields")
    return value


def _id(value: Any, pattern: re.Pattern[str], description: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"Invalid {description}")
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _check_dir(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"Symlink directory refused: {path.name}")
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise PermissionError(f"Catalog directory must be owned by user and private: {path.name}")


def _ensure_dir(path: Path, *, parents: bool = False) -> None:
    if path.is_symlink():
        raise ValueError(f"Symlink directory refused: {path.name}")
    path.mkdir(mode=0o700, parents=parents, exist_ok=True)
    _check_dir(path)


def _maybe_dir(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    _check_dir(path)
    return True


def _read_json(path: Path) -> dict:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise PermissionError("Catalog record must be a private regular file")
        if info.st_size > MAX_FILE_BYTES:
            raise ValueError("Catalog record too large")
        with os.fdopen(fd, "rb", closefd=False) as reader:
            raw = reader.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("Catalog record exceeds byte cap")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("Catalog record must be JSON object")
        return value
    finally:
        os.close(fd)


def _create_record(path: Path, value: dict) -> None:
    """Write a private temp file + fsync, link without overwriting, fsync dir."""
    _check_dir(path.parent)
    raw = _canonical(value)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Catalog record exceeds 32 KiB")
    fd, tmp = tempfile.mkstemp(prefix=".new-record-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as writer:
            os.fchmod(writer.fileno(), 0o600)
            writer.write(raw)
            writer.flush()
            os.fsync(writer.fileno())
        os.link(tmp, path)   # Refuse replacement; history is append-only via API.
        dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        os.unlink(tmp)


class CatalogStore:
    """Per-robot filesystem catalog; no daemon/background actions.

    All mutating operations take the same exclusive robot-scoped file lock.
    A process in the same Unix account may access this data; it is not a
    remote authorization mechanism.
    """

    def __init__(self, root: Path | str, robot_id: str):
        self.root = Path(root).expanduser()
        self.robot_id = _id(robot_id, ROBOT_ID, "robot_id")
        self.robot_dir = self.root / self.robot_id
        self.proposals_dir = self.robot_dir / "proposals"
        self.rejected_dir = self.robot_dir / "rejected"
        self.expressions_dir = self.robot_dir / "expressions"

    def _init_for_write(self) -> None:
        _ensure_dir(self.root, parents=True)
        _ensure_dir(self.robot_dir)
        for folder in (self.proposals_dir, self.rejected_dir, self.expressions_dir):
            _ensure_dir(folder)

    def _check_existing(self) -> bool:
        if not _maybe_dir(self.root):
            return False
        if not _maybe_dir(self.robot_dir):
            return False
        for folder in (self.proposals_dir, self.rejected_dir, self.expressions_dir):
            if folder.exists() or folder.is_symlink():
                _check_dir(folder)
        return True

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self._init_for_write()
        fd = os.open(self.robot_dir / ".catalog.lock",
                     os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise PermissionError("Lock file must be owned by user and private")
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _pending_file(self, proposal_id: str) -> Path:
        return self.proposals_dir / (_id(proposal_id, HEX_ID, "proposal_id") + ".json")

    def _rejected_file(self, proposal_id: str) -> Path:
        return self.rejected_dir / (_id(proposal_id, HEX_ID, "proposal_id") + ".json")

    def _revision_dir(self, expression_id: str) -> Path:
        return self.expressions_dir / _id(expression_id, EXPR_ID, "expression_id")

    def history(self, expression_id: str) -> list[dict]:
        path = self._revision_dir(expression_id)
        if not self._check_existing() or not _maybe_dir(path):
            return []
        filenames = sorted(p.name for p in path.iterdir() if REVISION_FILE.fullmatch(p.name))
        if len(filenames) > MAX_REVISIONS_PER_ID:
            raise ValueError("Too many catalog revisions")
        out: list[dict] = []
        previous: str | None = None
        for index, filename in enumerate(filenames, start=1):
            match = REVISION_FILE.fullmatch(filename)
            if not match or int(match.group(1)) != index:
                raise ValueError("Missing or reordered catalog revision")
            record = _read_json(path / filename)
            _exact(record, {
                "schema_version", "robot_id", "expression_id", "revision",
                "action", "source_proposal_id", "rollback_source_revision",
                "previous_record_sha256", "expression_sha256", "expression",
                "created_at_utc", "actor_kind", "preview_only",
                "hardware_execution_authorized",
            }, "revision")
            if (record["schema_version"] != HISTORY_SCHEMA
                    or record["robot_id"] != self.robot_id
                    or record["expression_id"] != expression_id
                    or type(record["revision"]) is not int
                    or record["revision"] != index
                    or record["previous_record_sha256"] != previous
                    or record["actor_kind"] != "explicit_local_cli_action"
                    or record["preview_only"] is not True
                    or record["hardware_execution_authorized"] is not False):
                raise ValueError("Broken catalog revision identity/chain")
            expression = validate_expression(record["expression"])
            if expression["expression_id"] != expression_id or record["expression_sha256"] != _digest(expression):
                raise ValueError("Catalog recipe integrity mismatch")
            if record["action"] == "approve":
                _id(record["source_proposal_id"], HEX_ID, "source_proposal_id")
                if record["rollback_source_revision"] is not None:
                    raise ValueError("Approval cannot refer to rollback target")
            elif record["action"] == "rollback":
                if (record["source_proposal_id"] is not None
                        or type(record["rollback_source_revision"]) is not int
                        or not 1 <= record["rollback_source_revision"] < index
                        or expression != out[record["rollback_source_revision"] - 1]["expression"]):
                    raise ValueError("Invalid rollback provenance")
            else:
                raise ValueError("Unknown revision action")
            previous = _digest(record)
            out.append(record)
        return out

    def list_catalog(self) -> list[dict]:
        if not self._check_existing() or not _maybe_dir(self.expressions_dir):
            return []
        folders = sorted(p for p in self.expressions_dir.iterdir())
        if len(folders) > MAX_CATALOG_ENTRIES:
            raise ValueError("Catalog capacity exceeded")
        items = []
        for path in folders:
            expression_id = _id(path.name, EXPR_ID, "stored expression id")
            records = self.history(expression_id)
            if records:
                latest = records[-1]
                items.append({
                    "expression_id": expression_id,
                    "label": latest["expression"]["label"],
                    "revision": latest["revision"],
                    "origin": latest["expression"]["origin"],
                    "last_action": latest["action"],
                    "preview_only": True,
                    "hardware_execution_authorized": False,
                })
        return items

    def show(self, expression_id: str) -> dict:
        records = self.history(expression_id)
        if not records:
            raise ValueError("Unknown catalog expression")
        return deepcopy(records[-1])

    def _approval_for(self, proposal_id: str) -> dict | None:
        # The immutable approval revision is the decision; a crash cannot
        # duplicate it by losing a separate mutable "approved" index.
        if not self._check_existing() or not _maybe_dir(self.expressions_dir):
            return None
        for path in self.expressions_dir.iterdir():
            records = self.history(path.name)
            for record in records:
                if record["action"] == "approve" and record["source_proposal_id"] == proposal_id:
                    return record
        return None

    def list_proposals(self) -> list[dict]:
        if not self._check_existing() or not _maybe_dir(self.proposals_dir):
            return []
        filenames = sorted(self.proposals_dir.glob("*.json"))
        if len(filenames) > MAX_PROPOSALS:
            raise ValueError("Too many queued proposals")
        items = []
        for path in filenames:
            _id(path.stem, HEX_ID, "proposal filename")
            item = self._load_proposal(path.stem)
            approved = self._approval_for(path.stem)
            rejected = self._rejected_file(path.stem).exists()
            if rejected and approved:
                raise ValueError("Conflicting catalog decisions")
            items.append({
                "proposal_id": path.stem,
                "expression_id": item["expression"]["expression_id"],
                "source_kind": item["source_kind"],
                "submitted_at_utc": item["submitted_at_utc"],
                "status": "approved" if approved else "rejected" if rejected else "pending",
                "approval_revision": approved["revision"] if approved else None,
            })
        return items

    def _load_proposal(self, proposal_id: str) -> dict:
        record = _read_json(self._pending_file(proposal_id))
        _exact(record, {"schema_version", "robot_id", "proposal_id", "source_kind",
                        "source_envelope", "expression", "expression_sha256",
                        "submitted_at_utc", "hardware_execution_authorized",
                        "approval_required_for_persistence"}, "stored proposal")
        if (record["schema_version"] != PENDING_SCHEMA
                or record["robot_id"] != self.robot_id
                or record["proposal_id"] != proposal_id
                or record["hardware_execution_authorized"] is not False
                or record["approval_required_for_persistence"] is not True):
            raise ValueError("Invalid proposal identity")
        expression = validate_expression(record["expression"])
        if record["expression_sha256"] != _digest(expression):
            raise ValueError("Proposal recipe hash mismatch")
        if record["source_kind"] == "cognitive_proposal":
            envelope = validate_proposal(record["source_envelope"])
            if (envelope["proposal_id"] != proposal_id
                    or envelope["robot_id"] != self.robot_id
                    or envelope["expression"] != expression):
                raise ValueError("Cognitive envelope does not match proposal")
        elif record["source_kind"] == "operator":
            if record["source_envelope"] is not None or expression["origin"] != "operator":
                raise ValueError("Operator proposal has invalid origin")
        else:
            raise ValueError("Unknown proposal origin")
        return record

    def queue(self, candidate: dict) -> dict:
        if not isinstance(candidate, dict):
            raise ValueError("Candidate must be an object")
        if "contract" in candidate:
            envelope = validate_proposal(candidate)
            if envelope["robot_id"] != self.robot_id:
                raise ValueError("Cognitive proposal robot mismatch")
            source_kind = "cognitive_proposal"
            proposal_id = envelope["proposal_id"]
            expression = envelope["expression"]
            source_envelope = deepcopy(envelope)
        else:
            expression = validate_expression(candidate)
            if expression["origin"] != "operator":
                raise ValueError("Unwrapped Cognitive expressions cannot enter catalog")
            source_kind = "operator"
            proposal_id = uuid.uuid4().hex
            source_envelope = None
        with self._locked():
            if len(list(self.proposals_dir.glob("*.json"))) >= MAX_PROPOSALS:
                raise ValueError("Catalog proposal queue at capacity")
            if self._pending_file(proposal_id).exists():
                raise ValueError("Proposal ID replayed; already submitted")
            record = {
                "schema_version": PENDING_SCHEMA,
                "robot_id": self.robot_id,
                "proposal_id": proposal_id,
                "source_kind": source_kind,
                "source_envelope": source_envelope,
                "expression": deepcopy(expression),
                "expression_sha256": _digest(expression),
                "submitted_at_utc": _utc(),
                "hardware_execution_authorized": False,
                "approval_required_for_persistence": True,
            }
            _create_record(self._pending_file(proposal_id), record)
        return {
            "proposal_id": proposal_id, "expression_id": expression["expression_id"],
            "status": "pending", "persistence_performed": True,
            "hardware_commands_sent": False,
            "hardware_execution_authorized": False,
        }

    def approve(self, proposal_id: str, *, expected_revision: int, confirmation: str) -> dict:
        _id(proposal_id, HEX_ID, "proposal_id")
        if confirmation != f"APPROVE {self.robot_id} {proposal_id}":
            raise PermissionError("Explicit local operator approval phrase required")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("Expected revision must be non-negative integer")
        with self._locked():
            candidate = self._load_proposal(proposal_id)
            if self._rejected_file(proposal_id).exists():
                raise ValueError("Rejected proposal cannot be approved")
            if self._approval_for(proposal_id):
                raise ValueError("Proposal already approved; replay refused")
            expression = candidate["expression"]
            expression_id = expression["expression_id"]
            existing = self.history(expression_id)
            if len(existing) != expected_revision:
                raise ValueError("Stale expected revision; check current history")
            if not existing and len(self.list_catalog()) >= MAX_CATALOG_ENTRIES:
                raise ValueError("Catalog full")
            record = self._record(expression, len(existing) + 1, "approve",
                                  proposal_id, None, existing)
            folder = self._revision_dir(expression_id)
            _ensure_dir(folder)
            _create_record(folder / f"rev-{record['revision']:06d}.json", record)
        return self._receipt(record)

    def reject(self, proposal_id: str, *, reason: str, confirmation: str) -> dict:
        _id(proposal_id, HEX_ID, "proposal_id")
        if confirmation != f"REJECT {self.robot_id} {proposal_id}":
            raise PermissionError("Explicit rejection confirmation required")
        if (not isinstance(reason, str) or not 1 <= len(reason) <= 160
                or any(ord(c) < 32 or ord(c) == 127 for c in reason)):
            raise ValueError("Rejection reason must be a short single line")
        with self._locked():
            self._load_proposal(proposal_id)
            if self._approval_for(proposal_id):
                raise ValueError("Approved proposal cannot be rejected")
            record = {
                "schema_version": REJECTION_SCHEMA,
                "robot_id": self.robot_id, "proposal_id": proposal_id,
                "reason": reason, "decision_at_utc": _utc(),
                "actor_kind": "explicit_local_cli_action",
                "hardware_execution_authorized": False,
            }
            _create_record(self._rejected_file(proposal_id), record)
        return {"proposal_id": proposal_id, "status": "rejected",
                "hardware_commands_sent": False, "persistence_performed": True}

    def rollback(self, expression_id: str, *, to_revision: int,
                 expected_revision: int, confirmation: str) -> dict:
        _id(expression_id, EXPR_ID, "expression_id")
        if confirmation != f"ROLLBACK {self.robot_id} {expression_id} TO {to_revision}":
            raise PermissionError("Explicit rollback confirmation required")
        if type(to_revision) is not int or type(expected_revision) is not int:
            raise ValueError("Revision must be integer")
        with self._locked():
            history = self.history(expression_id)
            if (len(history) != expected_revision or not 1 <= to_revision < len(history)):
                raise ValueError("Invalid/stale rollback revision")
            expression = deepcopy(history[to_revision - 1]["expression"])
            record = self._record(expression, len(history) + 1, "rollback",
                                  None, to_revision, history)
            _create_record(self._revision_dir(expression_id) /
                           f"rev-{record['revision']:06d}.json", record)
        return self._receipt(record)

    def _record(self, expression: dict, revision: int, action: str,
                proposal_id: str | None, rollback_target: int | None,
                existing: list[dict]) -> dict:
        if revision > MAX_REVISIONS_PER_ID:
            raise ValueError("Revision limit reached")
        return {
            "schema_version": HISTORY_SCHEMA,
            "robot_id": self.robot_id,
            "expression_id": expression["expression_id"],
            "revision": revision,
            "action": action,
            "source_proposal_id": proposal_id,
            "rollback_source_revision": rollback_target,
            "previous_record_sha256": _digest(existing[-1]) if existing else None,
            "expression_sha256": _digest(expression),
            "expression": deepcopy(expression),
            "created_at_utc": _utc(),
            "actor_kind": "explicit_local_cli_action",
            "preview_only": True,
            "hardware_execution_authorized": False,
        }

    @staticmethod
    def _receipt(record: dict) -> dict:
        return {
            "robot_id": record["robot_id"],
            "expression_id": record["expression_id"],
            "revision": record["revision"], "action": record["action"],
            "catalog_revision_saved": True,
            "scene_profile_modified": False, "service_restarted": False,
            "hardware_commands_sent": False, "hardware_execution_authorized": False,
        }
