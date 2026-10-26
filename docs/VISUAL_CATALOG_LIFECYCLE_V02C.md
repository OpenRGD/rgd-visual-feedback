# VISUAL-0.2C — Local Expression Catalog (candidate)

**Status:** source implementation proposed on a separate draft branch. **No integration with the live BLE systemd service, Console, real Cognitive System or physical displays.**

## Goal and ownership

Allow Paky-02 (and later any robot) to accumulate **named declarative eye expressions** without changing the renderer's source code. The catalog belongs to `OpenRGD/rgd-visual-feedback`. The operator's CLI explicitly decides what data enters a local approved catalog; Voice Studio remains separate.

The live Paky-01 RGB config remains untouched at `~/.config/paky-visual-feedback/config.json`.

## Storage

Default per-user storage root:

```text
~/.local/share/openrgd/visual-feedback/catalogs/
└── paky-02/
    ├── .catalog.lock
    ├── proposals/
    │   └── <proposal_id>.json       # pending payload; immutable-by-protocol
    ├── rejected/
    │   └── <proposal_id>.json       # operator decision, no deletion
    └── expressions/
        └── curiosita_gentile/
            ├── rev-000001.json      # first approved version
            ├── rev-000002.json      # subsequent operator-approved recipe
            └── rev-000003.json      # rollback: new version based on older recipe
```

New directories are private `0700`, files `0600`, operations use a per-robot advisory Linux `flock`, private temporary files and atomic `link` without overwriting existing revisions. Writes call `fsync` on data and directory.

The application is **append-only by protocol**. An ordinary Unix user who owns the files can still edit/delete them; these hashes are **not signatures, canonical Chronons, legal evidence or an off-device backup**. The current implementation requires reviewing the owner/permission context and should not be exposed as a network endpoint.

## Operator workflow

Use a separate checkout/worktree, not the clone that runs systemd. For a first trial, keep all state in a disposable `mktemp -d` root, e.g. `--root "$CATALOG_TEST_ROOT"`. The CLI runs without installing any daemon or changing config.

```bash
cd ~/openrgd/repos/rgd-visual-catalog-v02c-review
ROOT="$HOME/openrgd/visual-catalog-sandbox"  # optional local sandbox; NOT the live LED configuration

python3 scripts/visual_catalog.py --robot paky-02 --root "$ROOT" list

python3 scripts/visual_catalog.py --robot paky-02 --root "$ROOT" queue \
  --file examples/expressions/cognitive-curiosita-gentile.proposal.json

python3 scripts/visual_catalog.py --robot paky-02 --root "$ROOT" pending
```

The returned `proposal_id` must be copied into a deliberate approval action. For a **first** catalog revision, the expected current revision is 0:

```bash
python3 scripts/visual_catalog.py --robot paky-02 --root "$ROOT" approve \
  --proposal "<ID_FROM_QUEUE>" \
  --expected-revision 0 \
  --confirm "APPROVE paky-02 <ID_FROM_QUEUE>"
```

Show versions:

```bash
python3 scripts/visual_catalog.py --robot paky-02 --root "$ROOT" list
python3 scripts/visual_catalog.py --robot paky-02 --root "$ROOT" history \
  --expression curiosita_gentile
```

To roll back a recipe with 2 existing revisions, the operator requests the older revision **as a new revision 3**:

```bash
python3 scripts/visual_catalog.py --robot paky-02 --root "$ROOT" rollback \
  --expression curiosita_gentile --to-revision 1 --expected-revision 2 \
  --confirm "ROLLBACK paky-02 curiosita_gentile TO 1"
```

A rejected proposal remains available for audit, cannot subsequently be approved, and never changes the approved catalog. The operator confirmation string is a guard against accidental terminal commands, **not user identity authentication**.

## Critical safety semantics

- `queue` persists only an **unapproved pending proposal**. A new cognitive emotion label, such as `curiosita_gentile`, does **not** automatically become an approved expression.
- `approve` persists only a catalog **recipe**. It **does not assign a scene**, grant live rendering or motion/LED/display authority, restart a service or communicate with the Cognitive System.
- `rollback` creates a new revision; it does **not** affect the robot's current LED state, previously exported scene or physical display.
- A cognitive proposal must provide the complete existing `openrgd.visual.cognitive-expression-proposal.v0.1-candidate` wrapper and pass validation, including the matching `robot_id`. A bare recipe with `origin=cognitive_proposal` cannot be queued as operator content.
- Stored producer identities in JSON are **untrusted declarations**. This is a direct, locally initiated CLI tool. A future Cognitive ingress requires separate authenticated transport and replay/authorization policy.
- Catalog records preserve payload digests and hash-chain links. This detects accidental modifications to records and later chain links, but the latest record can be rewritten by someone with the same Unix account; cryptographic attestation would need a separate trusted store/signature.
- There is no `POST /catalog` endpoint, no bridge mounted in the Console Docker container, no `eval`/code execution, no display/device discovery and no physical light/sound measurement.

## Version conflict and scalability

An approval supplies `--expected-revision`; a stale value is rejected rather than overwriting another decision. Record files never change; `revision=N+1` becomes latest. This initial bounded implementation supports up to 256 named expressions per robot, 512 revisions per expression, and 4096 queued proposals before a separately reviewed retention strategy is required. The Visual Studio profile preview continues to support **32 active recipes per scene configuration**. Long-term repertoire archiving, garbage collection, quota policies and backups are not included.

## Exit gates and subsequent Console wave

- Offline tests for queue/approve/reject/rollback, restart persistence, revision-chain integrity, private storage permissions, explicit operator confirmation, missing/duplicate source IDs and cross-robot requests.
- Paky-01/02 manual sandbox smoke test with no live service restart.
- Before a Console editing interface: authenticated host-side catalog service, constrained operator approval API, CSRF/access control, conflict responses, robust on-disk migration and secure history/audit must be designed and tested. Do not bind-mount this user catalog into Module Agent.
- Before physical display output: verified PERIPH binding, safe frame renderer, TTL/arbitration, hardware capability checking and a separate rollout approval.

**Operator-approved catalog entry != a deployed or safe hardware effect.**
