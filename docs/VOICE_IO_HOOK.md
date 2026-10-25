# Voice I/O -> Visual Feedback v0.2 (planned integration)

No modifications have been made to the Voice I/O repository or its event bus.

Call the local CLI when the corresponding **real lifecycle event** occurs:

| Real voice event | Visual state |
| --- | --- |
| microphone/STT active listening | listening |
| end of utterance; model request starts | thinking |
| playback actually starts (not when TTS text is requested) | speaking |
| playback ends; ready for wake/listening | idle (or listening if mic immediately resumes) |
| voice service fault requiring attention | error |

Minimal example from Python (non-blocking to the main thread if used with asyncio):

```python
import asyncio

async def set_visual_state(state: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "paky-led", state,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.wait(), timeout=2)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
```

Or use the local Unix socket directly, without spawning a process:

```
PATH = $XDG_RUNTIME_DIR/paky01-visual-feedback.sock
REQUEST  = {"version":1,"command":"set_state","state":"listening"}\n
RESPONSE = {"ok":true,"accepted":true,"desired":"listening","connected":true}\n
```

The response `accepted:true` means the request entered the output state machine, not that a physical LED transition was observed. Use `paky-led status` to see `applied` when BLE is available.

This is a **local peripheral output**. It must never be treated as proof that motor state, safety, or perception succeeded.
