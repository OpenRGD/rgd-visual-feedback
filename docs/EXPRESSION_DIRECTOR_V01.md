# VISUAL — Expression Director v0.1

**Candidate / offline / non-actuating.** Builds on Eye Composer PR #10 at `bdb64dac3845e6a8a1ac473c7d6013451a8490b0`, generic pack PR #8, and the behavior specification in Paky-01 PR #7. VISUAL-RI-01 PR #11 stays independent on main; no change to RI, Core, Console, Voice IPC, BLE, catalog or physical rendering.

## Responsibility

The Director is a **session-scoped temporal layer above the existing pure Eye Composer**. It does not change any expression recipe, rendering algorithm, color, scene matcher or compatibility matrix. The Composer remains the sole authority for compatibility of gestures and functional state in this synthetic preview. Functional phase, microphone/playback evidence, display availability, gaze and reduced-motion policy are evaluated anew on each step. No physical or authenticated evidence is supplied.

## Session and temporal policy

- One instance per explicit synthetic robot/session ID; strictly increasing frame sequence and non-regressing caller-provided monotonic time. Complete snapshots, not event deltas. The input is the existing composer contract nested in a new candidate step envelope, with gesture explicitly null; the Director alone injects an admitted gesture. The optional request has an ID, named scene and original requested monotonic timestamp. The step schema references the existing composer schema; no network resolution is necessary (test registry loads it locally).
- Existing source sample timestamps (Voice/microphone/gaze) are preserved; exact repeats cannot renew freshness. Reject regressions, conflicting samples at same timestamp, or revival of a withdrawn sample without a strictly newer sample. A null snapshot means withdrawn. Validation is transactional: rejected steps do not advance sequence, burn IDs or output a new scene. No autonomous watchdog on invalid input.
- One active gesture, no queue; among compatible gestures equal priority and latest admissible request wins. An incompatible/expired/late request is consumed, but does not replace a compatible active gesture. Once interrupted/expired/replaced the ID cannot replay. Use original request time as clip start, not receipt time; requests older than previous tick are too late. Exact repeats, even if restamped or edited, cannot renew a clip. A compatible phase change may preserve a current clip until expiry; expiry returns to current phase, not old scene.
- Memory bounded at 256 distinct consumed gesture IDs (including denied ones). Never evict old IDs. At capacity refuse new gestures while functional composition continues. New session is explicit and separate; no durable replay protection or authentication across restarts. Caller must serialize steps.
- Reuse the Composer's existing synthetic 2000 ms Voice/mic and 700 ms gaze ages; no new time constants other than bounded replay memory. Functional 12 s recipe duration is not a TTL. No interpolated gaze return or real animation scheduler; expired gaze has centered intent, and decorative policy remains in Composer.
- Director results have a separate schema version label, decision/transition, active/ended ID and nested **unchanged** Eye Composer result. All hardware/physical/source authentication flags false. No RI refs or report input, no derived attention authorization, no Chronicle/History commit. Schema validation only checks structural input; Python checks cross-frame temporal and identity semantics.

## Test on a separate worktree

```bash
python3 scripts/expression_director_preview.py
python3 scripts/expression_director_preview.py --frame-index 0 > /tmp/director-frame.json
```

Timeline (all fictional, no wait/sleep): 0 speaking + friendly admitted; 1 duplicate ignored; 2 current phase idle with compatible gesture; 3 gesture expires; 4 curious admitted; 5 error interrupts; 6 replay of curious denied; 7 unchanged old Voice sample expires and yields connecting / ring off. Export any frame as the original Eye Composer result for Console PR #18's Eye Composition Preview; no browser policy engine or new UI required.

## Boundaries and future gates

This is not a live Expression Director service. No authentic source timestamps, producer turn IDs, independent sticky alarms, acquisition/playback verification, cross-session replay store, persistence, authorization, or hardware delivery. A late event restamped as a new sample cannot be identified by this preview: real turn correlation remains a separate Voice integration gate. No operational display handshake/watchdog/physical acknowledgement, and no automatic relation between RI hash verification and gaze admission. Core Feedback PR #6 and RI contracts remain candidates. Any later live bridge requires explicit source/robot/session/clock/quality/TTL/authority review and independent tests; do not run this as a daemon or bind it to actual hardware.
