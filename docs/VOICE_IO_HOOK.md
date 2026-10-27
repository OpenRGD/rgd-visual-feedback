# Voice I/O → Visual Feedback — explicit lifecycle integration (v0.3 candidate)

**Status:** The Visual Feedback v0.2 BLE service has been operator-tested on Paky-01. This v0.3 candidate adds an **optional** local event-ingress command and synthetic tests. It has **not** been deployed or validated against a running Voice Studio instance. The `rgd-voice` repository is published, and its PR #2 contains an optional producer, but **the two live services have not been physically commissioned together**; this document is an implementation contract, not LED acceptance evidence.

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
5. Reconcile the event names with the now-published `OpenRGD/rgd-voice` candidate: [Voice PR #2](https://github.com/OpenRGD/rgd-voice/pull/2) provides the optional Unix sender and real legacy VAD PCM/STT callbacks; [Voice PR #4](https://github.com/OpenRGD/rgd-voice/pull/4) separately covers native HTML audio playback.
6. Test playback start/end, reconnect, rapid turn-taking, no-response, duplicate, stale-session, and BLE-disconnected cases **on the mini-PC**, then tag a release.

## Operator rollout (NOT automatic)

Nothing in this PR modifies the currently running v0.2 systemd service. After merge and review, update the cloned Visual repo on Paky-01 and explicitly restart `systemctl --user restart paky01-visual-feedback` only at a convenient maintenance point. Verify the old `paky-led` CLI first, then emit synthetic voice events on the updated daemon. A live Voice Studio connection remains pending until its code is available.

A deliberate synthetic smoke test is included. It prints events without contacting any service by default:

```bash
python3 scripts/voice_event_smoke.py            # dry run; no LED effect
python3 scripts/voice_event_smoke.py --apply    # explicitly sends events (updated v0.3 daemon only)
```

This is **not** a substitute for actual Voice Studio lifecycle evidence.

**Safety:** Visual states are UI effects, not motor/boot readiness, perception accuracy, safety authorization or Chronon evidence.

## VOICE-0.4D commissioning reference (2026-10-26)

The Voice team has provided a reversible hardware canary at [VOICE-0.4D real lifecycle](https://github.com/OpenRGD/rgd-voice/blob/feat/visual-feedback-lifecycle-v0.3.2/docs/VOICE-0.4D-REAL-LIFECYCLE-CANARY.md). Its read-only monitor reports desired, applied and BLE connected independently while the *existing* v0.2 systemd user service is deliberately paused and a v0.3 candidate daemon is run in the foreground. This repository remains sole owner of BLE; no extra LED driver is added to Voice.

Keep this PR **Draft** until real BC-Master VAD, Whisper, actual Bose playback and visible LED transitions have been observed on Paky-01. Do not run two Voice producer sessions (browser preview and foreground VAD) concurrently with this one-session gate. Browser/PCM are not physical microphone/speaker attestations.
