# GPU voice and reliability upgrade

## Running this build

Restart JARVIS after updating. Kokoro now uses CUDA when available. The startup
console reports `[TTS] Kokoro device: cuda (NVIDIA GeForce RTX 3060)`.
Ollama continues running on the home server; speech generation runs on this PC.
Speech recognition remains on CPU.

The installed Windows environment was upgraded to PyTorch 2.14.0+cu130 and CUDA
availability was verified on the RTX 3060 12 GB. For a fresh environment, install
the appropriate CUDA build using https://pytorch.org/get-started/locally/ after
installing the project requirements. No driver or global CUDA toolkit was changed.

The optional `tts_device` setting in local `config/api_keys.json` accepts `auto`
(default), `cuda`, or `cpu`. Restart after changing it. Use `cpu` if sharing the GPU
with a game causes stutter. Explicit `cuda` reports an error when unavailable;
`auto` falls back to CPU. Never commit this local configuration file.

## Changes

- Text appears sentence by sentence without waiting for speech synthesis or the
  complete turn. Speech generation runs in its own ordered queue.
- Explicit weather, system, file, screen and memory requests can skip the model
  routing call. Ambiguous requests retain model routing with a smaller context.
- Simple screen questions return the vision model's answer directly, avoiding a
  second model pass. Screen capture includes all displays by default; request
  monitor 1 or monitor 2 to focus on one display and improve small-text readability.
- Identity settings refresh on the next request. Supported name-memory updates
  also update the configured user name.
- File creation refuses existing filenames. A collision stops later calls in the
  same batch and subsequent model steps. Create and replacement writes read the
  saved content back before reporting verification.
- A selected tool request cannot immediately announce success without a tool
  call: it gets one corrective retry, then reports failure if no call is produced.
  This does not prove that every step of an arbitrary complex task was completed.
- Recognition rejects low-confidence/no-speech segments and rechecks the known
  vocabulary-list echo without vocabulary hints. Real microphone testing is still
  needed; this is not a guarantee against every transcription error.
- News and research can read up to two source pages concurrently. Page excerpts,
  search-provider dates and publication metadata are distinguished; missing dates
  are explicitly unverified. A page read is not independent corroboration.

## Validation and measured limits

- 57 automated tests passed, including text delivery while synthesis is blocked,
  file collision protection, readback, identity refresh, monitor selection,
  recognition filtering and direct vision replies.
- Live home-server tests created a scratch file, changed `high` to `hi`, and
  confirmed that a later create request did not overwrite it. Weather and system
  status tools also returned live data. Public NASA page reading was exercised.
- For one identical approximately 5.45-second spoken sentence, warm CUDA Kokoro
  synthesis measured 0.330–0.345 seconds versus 2.206–5.301 seconds on CPU. The
  first CUDA synthesis took 2.263 seconds. These are local samples, not a general
  end-to-end speed guarantee or a controlled gaming benchmark.
- PyTorch reserved approximately 798 MiB during that GPU test; driver/context
  overhead and other GPU applications consume additional memory. Gaming FPS and
  frame-time impact have not been measured.
- Server inference still determines much of response latency. Faster voice and
  fewer routing calls do not remove the model's reasoning or tool-use limitations.
