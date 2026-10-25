# Voice I/O → Visual Feedback — explicit lifecycle integration (v0.3 candidate)

**Status:** The Visual Feedback v0.2 BLE service has been operator-tested on Paky-01. This v0.3 candidate adds an **optional** local event-ingress command and synthetic tests. It has **not** been deployed or validated against a running Voice Studio instance. The `rgd-voice` producer is not yet published; this document is an implementation contract, not evidence of an end-to-end live connection.

## No duplicated hardware owner

- Voice Studio reports real lifecycle changes and never accesses BLE hardware.
- Visual Feedback remains the **only** BLE connection owner.
- Both the legacy `set_state` command and `paky-led` CLI remain compatible.
- The new `voice_event` command uses the *same* 0600 Unix socket at `$XDG_RUNTIME_DIR/paky01-visual-feedback.sock`, not a network port.
- All transitions update a **desired state**; they do not certify physical LED output.

## Event-to-state contract

| Actual producer event | Visual state | Emission point |
| --- | --- | --- |
| `listening.started` | `listening` | Microphone/STT is actually accepting speech |
| `inference.started` | `thinking` | Model call genuinely begins |
| `playback.started` | `speaking` | Audio playback has *actually started* |
| `playback.ended` | `idle` | Last playback sample completed |
| `voice.error` | `error` | Confirmed operational fault |
| `voice.ready` | `idle` | Voice service explicitly enters standby |

If the microphone becomes active again immediately after playback, emit `listening.started` as the **next** higher-sequence event. Do not infer talking from TTS generation or display text. Unknown events fail closed.

## Candidate IPC request

Each Voice Studio **process instance** generates a fresh 32-character hexadecimal session id, increments a non-negative sequence number for *every emitted lifecycle transition*, and serializes outgoing events in order:

```json
{
  "version": 1,
  "command": "voice_event",
  "schema_version": "openrgd.visual.voice-event.v0.1-candidate",
  "source": "rgd-voice",
  "session_id": "0123456789abcdef0123456789abcdef",
  "sequence": 1,
  "event": "listening.started"
}
```

Send exactly one newline-terminated JSON object to the existing local socket and read one newline-terminated reply. The request is strictly validated; extra fields are rejected. See `contracts/voice-event.v0.1-candidate.schema.json`.

Example successful acceptance (shape abbreviated):

```json
{"ok":true,"accepted":true,"desired":"listening","connected":true,"source_event":"listening.started","event_sequence":1}
```

A duplicate or stale request returns `ok:true,accepted:false,ignored:"duplicate_or_out_of_order"` (or `retired_session`). This is **not** a physical LED acknowledgment. `status` reports `desired` (requested), `applied` (BLE write succeeded) and `connected` independently; `voice_event` reports the last accepted logical source event.

The ordering guard is memory-only, remembers at most 32 retired producer sessions, and resets on Visual daemon restart. It does **not** authenticate callers or offer durable/canonical event history. The same-user Unix socket is the access boundary; any other production deployment needs an independent authorization design.

## Producer integration checklist

1. Connect to callbacks from *actual* STT/model/player lifecycle, not guessed timing.
2. Use a single ordered asynchronous event sender; do not block the audio callback, main playback thread, or deterministic robot runtime. Bound connect/read timeouts and treat Visual unavailability as nonfatal.
3. Generate a new session id when the voice producer starts/restarts. Keep sequence monotonic within the session.
4. Do not route errors from the LED subsystem back into Voice Studio's critical path.
5. Reconcile the new candidate event names with `OpenRGD/rgd-voice` when that repository has been published.
6. Test playback start/end, reconnect, rapid turn-taking, no-response, duplicate, stale-session, and BLE-disconnected cases **on the mini-PC**, then tag a release.

## Operator rollout (NOT automatic)

Nothing in this PR modifies the currently running v0.2 systemd service. After merge and review, update the cloned Visual repo on Paky-01 and explicitly restart `systemctl --user restart paky01-visual-feedback` only at a convenient maintenance point. Verify the old `paky-led` CLI first, then emit synthetic voice events on the updated daemon. A live Voice Studio connection remains pending until its code is available.

**Safety:** Visual states are UI effects, not motor/boot readiness, perception accuracy, safety authorization or Chronon evidence.
