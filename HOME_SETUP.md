# Mark-LIV with home Ollama

This fork uses **qwen3:8b** on your Ollama server for conversation, tool selection,
coding, document analysis, and memory summaries. **qwen3.5:9b** handles images
only, returning observations to the main model. Whisper speech recognition and
Kokoro speech generation run on the Windows PC's CPU. No Gemini key is needed.

The existing HUD, face/reactor toggle, lip-sync, colours, microphone/speaker
picker, push-to-talk, wake-word integration, phone dashboard, tools, plugins,
memory, undo, and confirmation UI remain connected to the runtime. Tools act on
the PC running the app; Ollama supplies reasoning, not remote desktop access.

## Install and launch

Use Python 3.11–3.13. From the repository directory on Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium firefox
.venv\Scripts\python.exe download_voices.py
.venv\Scripts\python.exe main.py
```

Enter your Ollama base URL in the existing first-run panel, for example
`http://YOUR-SERVER-IP:11434`. It is saved in ignored `config/api_keys.json`.
On the server, both `ollama pull qwen3:8b` and `ollama pull qwen3.5:9b` must
already have completed. Ollama must listen on the LAN interface and the server
firewall must allow the PC to connect. The app never starts a local Ollama server
or changes the remote server's settings.

On subsequent launches, double-click `Start-HomeAI.cmd`. It selects this
checkout's `.venv` and checks speech dependencies before opening the UI.
Each clone needs its own environment: installing packages in another copy of
Mark-LIV does not install them here. If a dependency is missing, the launcher
prints the repair command with the exact interpreter path to use.

`download_voices.py` downloads Whisper and Kokoro weights, seven voice presets,
and generates WAV previews in ignored `voice-samples/`. These are new local
voices, not copies of Gemini voices. Pick George or Fable for British English,
or Michael, Fenrir, Puck, Heart, or Bella for American English
in the existing customization panel. First-time setup requires internet; after
the models are cached, speech processing is local. These presets do not provide
Gemini's voices or full multilingual speech parity.

The download also caches a fixed startup greeting for every voice. English
startup greetings play without waiting for Ollama or loading PyTorch. The voice
model warms in the background for subsequent replies. Without a cached greeting,
the first launch must synthesize it once. Other languages keep the generated
greeting. Normal replies stream sentence by sentence while Ollama is generating,
and default to one or two sentences unless the request needs more detail.
Timing entries in the log measure sentence readiness and speech generation,
not the final speaker playback time. Ollama keeps its model loaded for 30 minutes
by default; set `llm_keep_alive` to change this.
Changing time and memory information is sent after the stable system prompt and
tool definitions so reconnects can reuse Ollama's prompt cache. A cold cache (or switching to the vision model)
can still make the first generated answer slow; the cached greeting remains
independent of that delay. Server timing logs separate load, prompt processing,
and answer generation.

Automatic startup news is displayed on screen without a model-generated spoken
summary, so it does not queue ahead of your questions. Set `startup_news_spoken`
to `true` to restore spoken news. The startup greeting still plays normally.
The model prepares its stable instruction/tool prefix in the background at
connection time, generating only one discarded token and executing no tools.
An immediate question may still wait for this preparation on a cold server.
Completed microphone transcripts appear immediately as separate log entries.
Timing diagnostics stay in the console; `First audio ready` includes speech
synthesis but excludes the audio driver's playback latency.

`tts_threads` defaults to 8, measured faster than 4 on the target PC. Short
spoken replies are cached in a bounded, voice-specific RAM cache, cleared when
the app closes. Only the fixed startup greeting is cached on disk.

Weather now uses [Open-Meteo](https://open-meteo.com/en/docs) to return current
temperature or a daily forecast without opening a browser. Use a city and full
state/country name. Ambiguous places require clarification; failed lookups do
not fall back to opening a webpage. US locations default to Fahrenheit.

## Configuration

Speech recognition defaults to Whisper `small` with `stt_beam_size: 3` for better
accuracy than the previous `base`/beam-1 setup. It runs locally on CPU and loads
in the background when connecting. This trades some recognition time and RAM
for accuracy. Existing explicit `stt_model` preferences remain respected.
`stt_vocabulary` accepts a short list of names or technical terms as spelling
hints. These do not forcibly replace recognized words. `stt_language` can be a
language code such as `en`; omit it for automatic language detection.

The audio buffer retains 250 ms before speech crosses the volume threshold to
preserve quiet opening sounds. The mic is still gated while the assistant is
speaking to avoid feedback: click Interrupt and wait for playback to stop before
speaking. These settings cannot guarantee recognition of unfamiliar names in
room noise; test with your own microphone after restarting.

See `config/home.example.json`. Merge settings into `config/api_keys.json`;
preserve existing plugin credentials and preferences. Never commit that file.
`HOMEAI_OLLAMA_URL` overrides the URL. For an authenticated proxy, set
`HOMEAI_OLLAMA_TOKEN` in the launching environment; do not put credentials in URLs.

Thinking is off by default for responsiveness. `thinking_enabled` turns it on;
`llm_max_tokens` may then need a larger budget. `llm_context` defaults to 16384
because the complete tool registry uses substantial prompt space. Lowering it
may improve speed but can truncate important instructions. GPU allocation is
left to the server rather than forced by the client.

Tool calls are checked against their declared JSON schemas and capped at 12
rounds per request. A broken connection does not automatically replay tool
actions. Long conversations retain recent complete exchanges; persistent facts
still use the original memory store. Voice changes preserve conversation.

## Differences and practical limits

- Web search uses live DDG results instead of Google's grounded-search API.
- Voice uses local utterance detection, transcription, and sentence-by-sentence
  synthesis; latency and turn-taking differ from Gemini Live. Its semantic
  background-speech filtering is not reproduced. Use push-to-talk in noisy rooms.
- Vision calls can load a second model on the RX 580, adding delay. Model requests
  are serialized. The main model stays `qwen3:8b`.
- Third-party services, OS actions, wake-word models, and plugins still need their
  original setup. Presence of a tool does not guarantee its external service works.
- The Google SDK remains installed for legacy schema objects used by bundled
  actions; the active runtime and generation helpers never construct its client.

## Verification

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests exercise multi-step tools with vision attachment, invalid arguments,
network recovery, and model routing. Hardware microphone, speaker, camera, and
third-party integrations need a real interactive check on the target PC.

Protocol references: [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling),
[Kokoro voices](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md).
