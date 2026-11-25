# VISUAL-RI-01 / RI-H06 — optional read-only reports

25 Nov 2026 · candidate, non-normative, non-actuating · no deployment.

## Baselines and audit

- Visual main `08a9f14b4114eff75987dda682e51975b7e617d3`: v0.2.0, exclusive Miracles.Star BLE owner, local Unix socket 0600. Voice #2 is merged; the six-event `openrgd.visual.voice-event.v0.1-candidate` ingress reports the last accepted session/sequence/event, not an authenticated or durable event log. `paky-led status` on Paky-01 previously returned connected/desired/applied and the Voice status fields. Installed commit and end-to-end actual Voice playback plus optical confirmation not reverified in this wave.
- Visual draft stack #3→#4→#5→#6→#7→#8→#10: Studio, recipes, catalog and history, universal 21-expression pack, pure synthetic Eye Composer. Console #18 stacked preview-only viewer. No changes to those stacks, Voice IPC, BLE, systemd, Catalog Manager, firmware or Somatic.
- [RI PR #4](https://github.com/OpenRGD/rgd-reality-ingress/pull/4) exact head `5372f758df79c93fc887f3858d878635447f4a4d`; [RI handoff](https://github.com/OpenRGD/rgd-reality-ingress/blob/5372f758df79c93fc887f3858d878635447f4a4d/docs/handoffs/RI-TO-VISUAL-FEEDBACK.md). The candidate RI ref is an observation metadata pointer, not a lifecycle event, derived PerceptionResult, attention proposal or authorization.
- [Core Feedback PR #6](https://github.com/OpenRGD/openrgd/pull/6) head `8de03266b61d4acb6a431ccf6e21ce621ece572b`: proposed FeedbackDeliveryReport requires cue, robot, peripheral, zone, effect IDs and reported_at_utc. Current status cannot truthfully supply these. Do not fabricate them or use an import time as report time.

## Minimum adapter

`rgd_visual.ri_report.project_status(snapshot, input_kind=...)` takes the exact legacy successful IPC status JSON, optionally including Voice gate state, and returns a local candidate `openrgd.visual.ri-status-report.v0.1-candidate` report bundle. It is a pure projection; no access to RI, clock, device, Unix socket, network, filesystem persistence, or command endpoints. No module changes in the running services. The adapter can be entirely absent.

- `visual.delivery.status_snapshot`: source owner Visual, last requested `desired`, last driver-reported `applied`, connection, reported-error boolean. `driver_ack_reported` refers ONLY to the last applied state, not a new ack, nor necessarily to current desired. `rendered_scene:null` because legacy ring status does not expose a rendered scene.
- `voice.lifecycle.last_accepted_report`: original declared source owner Voice, reported by Visual gate, existing session/sequence/event, never a fresh lifecycle transition. Omit if no event accepted. Source not authenticated. No audio content.
- Both records have `occurred_at:null`, `clock_domain_id:null` (not available in legacy IPC); no fake receipt or Chronograf time. Bundle freshness is unknown. No robot binding, observation ref, history or actuation authorization. `physical_output_observed:false` and `physical_observation_ref:null` always. Caller must explicitly classify input as unverified_snapshot/synthetic/replay; never live.
- Strict fields and size-bounded stdin. BLE address and raw error strings are discarded; only export the report to a separately authorized local metadata consumer. Session ID is correlation metadata, not authentication. No media, history write, automatic upload or RI ingestion. A scoped host/robot identity, consent/ACL and report admission policy are still needed before shared retention.
- This is a Visual-local candidate status projection; NOT an additional canonical shared feedback schema or a v0.4 generic observation. Do not wrap into camera/audio/generic sensor samples, invent observation IDs or insert into RI's EvidenceStore. If RI adopts a report collection later, agree a distinct report type / resolver with Core.

## Incoming derived attention: intentionally deferred

No direct RI→driver, RI→Eye Composer or RI→Voice input. The present RI ref has no authorized gaze vector, verified robot/frame, producer session, calibration, quality/uncertainty or sensor measurement timestamp. Hash verification is not physical provenance. Preview inputs currently permit synthetic flags only.

A later separate candidate bridge must accept a typed Cognition/Attention proposal with `derived_input_refs`, bound source/session/robot/frame, Perception processor/calibration/version and quality, qualified freshness/clock domain, TTL, replay/sequence checks and explicit arbiter admission. Missing, replayed, synthetic, restricted, stale or mismatched inputs must leave current Voice/error policy independent and fall back to neutral gaze. Existing 700 ms gaze/2000 ms Voice ages in Eye Composer are synthetic-preview values, not an operational watchdog. No new renderer, no new device ownership, no automatic actuator privileges. Renderer desired/scene/driver report/independent optical observation remain separate debug layers; Console #18 remains synthetic. Future Core delivery bridge requires actual cue correlation and time source.

## Tests

Pinned upstream schema files under tests/fixtures/ri only; verify Git blob hash and exercise actual JSON Schema in dedicated test-only CI. RI blob `3d92e074e71593bf6db0a735394c628ea131668d`; Core delivery blob `c041efa70c221edde09a3025b7c914c765ad7ab5`. No dependency on upstream runtime. Positive status projection, no-change gate/driver test, strict negatives, redaction, replay, mismatch, CLI bounds; verify report cannot pass either external candidate schema and a valid RI reference is rejected as legacy status. Original offline CI unchanged. Tests don't imply a live RI report importer exists.

## Optional operator pilot (not performed or automatically authorized)

In a separate reviewed checkout, no installation or restart. Run synthetic fixture first:

```bash
PYTHONPATH=src python3 -m rgd_visual.ri_report --input-kind synthetic \
  < tests/fixtures/ri/legacy-status.synthetic.json
```

If explicitly authorized by the operator, take one read-only status sample using the existing owner (no second BLE connection, no new socket privilege):

```bash
set -o pipefail
"$HOME/.local/bin/paky-led" status | \
  PYTHONPATH=src python3 -m rgd_visual.ri_report --input-kind unverified_snapshot
```

Expect the same desired/applied and connection values without device address, raw errors, physical claims or invented times. Independently observed light would require a separate authorized acquisition owner and correlation; do not infer it from a read. Stop if status fails or schema differs; no report is emitted. Rollback: stop using the optional command/remove review checkout. No daemon change to undo. No persistent file by default.

## Return decision

Candidate-compatible for offline report separation; no-go for live persistence, physical attestation or evidence-driven gaze. RI #4 remains pinned; master checklist RI-H06 to record return, RI-A08/A06/A04/A09 remain open. No merge or rollout without separate owner review.
