# VISUAL-0.2D — Read-only Expression Catalog Snapshot

**Status:** candidate, read-only, manually exported. No live Console connector, authenticated host endpoint, Cognitive System, BLE/USB/display access or effect deployment.

## Motivation

Paky-02's `curiosita_gentile` catalog has been physically operator-tested through three revisions:
`rev-1 approve` (synthetic cognitive proposal), `rev-2 approve` (operator modification) and `rev-3 rollback to rev-1`. The CLI and its durable storage work, but the Visual Effects Studio browser cannot read the private local store without a trust boundary.

This wave solves **offline inspection only**: the local CLI exports a scoped, bounded JSON snapshot; the operator manually chooses the file for a browser-local Catalog Manager. The app never mounts catalog directories or binds hardware sockets.

## Export contract

`openrgd.visual.catalog-snapshot.v0.1-candidate` is documented in `contracts/visual-catalog-snapshot.v0.1-candidate.schema.json`.

The export includes:
- `robot_id`, export timestamp, read-only mode and explicit no-hardware authorization.
- For each approved expression: exact revision numbers and the *already persisted* revision records, including the original declarative eye recipe, operator action (`approve/rollback`), the rollback's source revision and stored SHA-256/chain references.
- Pending/approved/rejected proposal **metadata plus the bounded expressive-eye recipe only**. No original Cognitive `source_envelope`, source session/sequence, body signals, secret keys, network address, physical device identifier, file-system path, voice text or API credentials.
- `integrity_validated_during_export:true` means the local `CatalogStore.history()` checked its stored hashes and revision chain before export. It does **not** mean the resulting file is signed, tamper-proof or independently attested after leaving the mini-PC; `reader_must_not_trust_as_attested:true` is mandatory.

The export performs no writes. It obtains a **shared, private local `flock`** (no creation of a lock file) to avoid inconsistent snapshots during a concurrent operator decision. If existing catalog permission/lock metadata is unsafe, export fails closed.

Limits: 64 expressions, 64 revisions per expression, 128 proposals per snapshot, and 2 MiB total. If the catalog grows beyond bounds, export a **single expression** with `--expression`; do not silently truncate history.

## Manual Paky-02 smoke

Run in a *separate reviewed worktree* after fetching this PR's branch:

```bash
cd ~/openrgd/repos/rgd-visual-catalog-snapshot-v02d-review
CATALOG_ROOT="$HOME/openrgd/visual-catalog-sandbox-v02c"
SNAPSHOT="$HOME/openrgd/paky02-catalog-review.snapshot.json"
umask 077
python3 scripts/visual_catalog.py --robot paky-02 --root "$CATALOG_ROOT" \
  snapshot --expression curiosita_gentile > "$SNAPSHOT"

python3 - "$SNAPSHOT" <<'PY'
import json, sys
from pathlib import Path
p=json.loads(Path(sys.argv[1]).read_text())
assert p["robot_id"]=="paky-02" and not p["hardware_execution_authorized"]
print("robot:",p["robot_id"])
for entry in p["expressions"]:
    print(entry["expression_id"],[r["revision"] for r in entry["revisions"]])
print("proposals:",[(x["status"],x["expression_id"]) for x in p["proposals"]])
print("preview_only:",p["preview_only"])
PY
```

**Expected user fixture:** `curiosita_gentile [1,2,3]` and two approved proposal metadata entries. The export may be copied locally into the browser via explicit File selection. No upload to a provider, no background sync and no catalog mutation occur.

Use `snapshot --without-proposals` to omit proposal metadata entirely.

## Future live delivery

Do **not** introduce a Console POST approval/rollback endpoint on this branch. Live reads and operator decisions require a separately authenticated host service, authorization scope, audit, conflict policy, anti-CSRF guard and source-of-truth semantics. A JSON snapshot is a point-in-time preview, not the authoritative live state.

CI covers missing/modified history, disabled writes, private local permissions, robot scope and snapshot schema.