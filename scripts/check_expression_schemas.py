#!/usr/bin/env python3
"""Isolated JSON Schema conformance for candidate expressive contracts.

Only CI/dev tooling requires jsonschema. The visual runtime has no added deps
and never imports this script for operation or startup.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from rgd_visual.catalog import CatalogStore

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts"
FIXTURES = ROOT / "examples" / "expressions"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check() -> None:
    names = [
        ("eye-expression.v0.1-candidate.schema.json",
         "meraviglia_curiosa.preview.json"),
        ("cognitive-expression-proposal.v0.1-candidate.schema.json",
         "cognitive-meraviglia.proposal.json"),
    ]
    validators = []
    for schema_file, fixture_file in names:
        schema = load(SCHEMAS / schema_file)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        fixture = load(FIXTURES / fixture_file)
        validator.validate(fixture)
        validators.append(validator)

    expression = load(FIXTURES / names[0][1])
    proposal = load(FIXTURES / names[1][1])
    # A second invented name must conform without changing schemas/software.
    validators[1].validate(load(FIXTURES / "cognitive-curiosita-gentile.proposal.json"))
    invalid_expression = [
        {"animation": {**expression["animation"], "blink_interval_ms": 100}},
        {"palette": {**expression["palette"], "ring_brightness_pct": 100}},
        {"eyes": {**expression["eyes"], "left": {**expression["eyes"]["left"], "openness": 5}}},
        {"preview_only": False},
        {"claims_emotion_as_internal_state": True},
        {"script": "exec('something')"},
    ]
    invalid_proposals = [
        {"hardware_execution_authorized": True},
        {"approval_required_for_persistence": False},
        {"presentation": "apply_now"},
        {"source_module": "unknown"},
        {"expression": {**proposal["expression"], "origin": "operator"}},
    ]
    for item in invalid_expression:
        try:
            validators[0].validate({**expression, **item})
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Expression schema accepted invalid patch keys: {tuple(item)}")
    for item in invalid_proposals:
        try:
            validators[1].validate({**proposal, **item})
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Cognitive schema accepted invalid patch keys: {tuple(item)}")
    # The original v0.1 scene schema is frozen; new eye targets live only
    # under an explicit v0.2 profile version.
    v01_schema = load(SCHEMAS / "visual-studio-profile.v0.1-candidate.schema.json")
    v02_schema = load(SCHEMAS / "visual-studio-profile.v0.2-candidate.schema.json")
    Draft202012Validator.check_schema(v01_schema)
    Draft202012Validator.check_schema(v02_schema)
    v01_validator = Draft202012Validator(v01_schema, format_checker=FormatChecker())
    v02_validator = Draft202012Validator(v02_schema, format_checker=FormatChecker())
    old_profile = load(ROOT / "profiles" / "paky01-studio.preview.json")
    new_profile = load(ROOT / "profiles" / "paky02-expressive-studio.preview.json")
    v01_validator.validate(old_profile)
    v02_validator.validate(new_profile)
    for invalid in [
        {**new_profile, "schema_version": "openrgd.visual-studio.profile.v0.1-candidate"},
        {**new_profile, "expressions": {}},
        {**new_profile, "preview_only": False},
    ]:
        if invalid["expressions"] == {}:
            # The reference is then absent from the catalog, which the
            # Python engine rejects. Validate this invariant separately.
            from rgd_visual.studio import validate_profile
            try:
                validate_profile(invalid)
            except ValueError:
                continue
            raise AssertionError("Engine accepted missing eye expression ref")
        try:
            v02_validator.validate(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError("v0.2 schema accepted wrong version or permissions")
    # Read-only portable catalog export conformance: only locally validated,
    # NO cognitive session envelope, no authenticated web API, no device data.
    snapshot_schema = load(SCHEMAS / "visual-catalog-snapshot.v0.1-candidate.schema.json")
    Draft202012Validator.check_schema(snapshot_schema)
    snapshot_validator = Draft202012Validator(snapshot_schema, format_checker=FormatChecker())
    with TemporaryDirectory(prefix="rgd-visual-schema-") as root:
        store = CatalogStore(Path(root) / "catalog", "paky-02")
        candidate = load(FIXTURES / "cognitive-curiosita-gentile.proposal.json")
        info = store.queue(candidate)
        snapshot_validator.validate(store.export_snapshot())
        store.approve(info["proposal_id"], expected_revision=0,
                      confirmation="APPROVE paky-02 " + info["proposal_id"])
        snapshot = store.export_snapshot()
        snapshot_validator.validate(snapshot)
        for invalid in (
            {**snapshot, "hardware_execution_authorized": True},
            {**snapshot, "export_mode": "write_to_robot"},
            {**snapshot, "source_envelope": {"credentials": "exposed"}},
        ):
            try:
                snapshot_validator.validate(invalid)
            except ValidationError:
                pass
            else:
                raise AssertionError("Snapshot schema accepted untrusted field or false authority")
    # Reusable robot-neutral expression pack (candidate, no hardware binding).
    pack_schema = load(SCHEMAS / "eye-pack.v0.1-candidate.schema.json")
    Draft202012Validator.check_schema(pack_schema)
    pack_validator = Draft202012Validator(pack_schema, format_checker=FormatChecker())
    pack = load(ROOT / "packs" / "eyes" / "core-v0.1.json")
    pack_validator.validate(pack)
    from rgd_visual.expression_packs import load_pack, preview_profile
    checked_pack = load_pack(ROOT / "packs" / "eyes" / "core-v0.1.json")
    preview_for_robot = preview_profile(checked_pack, "demo-robot")
    v02_validator.validate(preview_for_robot)
    from rgd_visual.studio import preview
    assert preview(preview_for_robot, "voice", "listening.started")["scene"] == "listening"
    for invalid in (
        {**pack, "robot_id": "paky-01"},
        {**pack, "expressions": {**pack["expressions"], "core_idle": {
            **pack["expressions"]["core_idle"], "preview_only": False
        }}},
        {**pack, "scene_expressions": {**pack["scene_expressions"], "idle": "missing"}},
    ):
        try:
            pack_validator.validate(invalid)
        except ValidationError:
            pass
        else:
            if invalid["scene_expressions"].get("idle") == "missing":
                # JSON Schema cannot check dynamic object key references.
                from rgd_visual.expression_packs import validate_pack
                try:
                    validate_pack(invalid)
                except ValueError:
                    continue
            raise AssertionError("Eye pack contract accepted an invalid candidate")
    # Synthetic composition is explicitly NOT a real producer ingress.
    compose_schema = load(SCHEMAS / "eye-compose-input.v0.1-candidate.schema.json")
    Draft202012Validator.check_schema(compose_schema)
    compose_validator = Draft202012Validator(compose_schema, format_checker=FormatChecker())
    case = load(FIXTURES / "eye-composition-speaking-friendly.synthetic.json")
    compose_validator.validate(case)
    from rgd_visual.eye_composition import compose_preview
    result = compose_preview(checked_pack, case)
    assert result["functional_scene"] == "speaking"
    assert result["gesture_status"] == "visible"
    assert result["ring_intent"]["color"] == "#00FF46"
    assert not result["hardware_commands_sent"]
    for invalid in (
        {**case, "source_kind": "trusted_producer"},
        {**case, "hardware_execution_authorized": True},
        {**case, "display": {**case["display"], "eyes_enabled": "yes"}},
        {**case, "gesture": {**case["gesture"], "scene": "system.exec"}},
    ):
        try:
            compose_validator.validate(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError("Composition schema accepted invalid or authority-bearing input")
    print("EYE COMPOSITION: synthetic fixture + 4 negative schema cases OK")

    print("SHARED EYE PACK: schema + generic robot preview + 3 invalid candidates OK")

    print("EXPRESSIVE CONTRACTS: 5 positive fixtures + 14 negative checks OK")
    print("CATALOG SNAPSHOT: pending/approved exports + 3 negative schemas OK")


if __name__ == "__main__":
    check()
