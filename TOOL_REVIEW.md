# Tool reliability and response-time review

Reviewed 2026-09-24. All 24 current tools remain available. The UI, local voice choices, microphone pipeline, and home Ollama connection are retained.

## Main changes

- Removed the startup model prefill that could hold the model lock while processing approximately 8,000 tokens before a user request.
- A bounded, non-thinking router selects up to four native tool definitions. Unrelated definitions are not sent on every turn. The router is capped at 64 output tokens and cannot supply the spoken answer.
- Replaced the large default conversation prompt with a concise voice prompt. Memory, time, configured identity, and tool availability still reach the answering model. Set `compact_tool_prompt` to `false` in the local configuration to use the legacy `core/prompt.txt` customization instead.
- Tool progress callbacks write to the log instead of becoming new user messages. This removes a source of repeated responses and repeated work.
- Searches return source snippets and URLs directly; there is no nested model summary. Comparison searches retrieve up to three items concurrently. Retrieval uses a six-second per-provider timeout; this is not a guaranteed whole-turn deadline.
- Tool arguments are validated before action handlers run. Empty handler responses no longer count as confirmed success. Tool timing is logged separately from model timing.
- Requested helper-model deadlines are now respected instead of being raised to a minimum of 180 seconds.

## Validation and measured results

42 automated tests pass. They include queued turns, interruptions, tool chaining, streamed speech, recognition hints, weather ambiguity, router behavior, invalid arguments, failed actions, archive traversal/overwrite rejection, and progress-message isolation. All 24 native schemas passed JSON Schema validation.

A final live run against the configured Qwen3:8B server produced:

| Request | Total text/tool time | Result |
|---|---:|---|
| Incineroar type | 6.31 seconds | Fire/Dark; no web search |
| Newport News current temperature | 8.77 seconds | Weather tool only; live temperature and feels-like reading |
| CPU/RAM status | 8.02 seconds | Local status tool only; measured values |

These are single-run observations, not average latency guarantees. They exclude microphone recognition, TTS generation, and audio playback. Search retrieval separately returned source links in 1.19 seconds. Model cache state, other server work, internet services, and conversation length affect latency.

A trial that let the routing model answer factual questions was rejected after an incorrect answer. The shipped router only selects tools; the normal answering model handles the response. This does not eliminate the underlying model's possibility of factual errors.

## Coverage of current tools

| Tool | Review/change | Verification and limits |
|---|---|---|
| system_status | Selected without unrelated tool definitions | Live CPU/RAM check; unavailable sensors remain unavailable |
| screen_process | Capture failures release the busy flag | Existing mocked vision/tool-chain test; real screen interpretation depends on vision model |
| close_camera | Retained existing camera shutdown path | Reviewed; no camera activation during this audit |
| manage_monitor | Failed/empty news fetch no longer suppresses checks for the rest of the day | Reviewed; actual scheduled alerts not triggered |
| shutdown_jarvis | Retained explicit shutdown action | Reviewed; not executed; session-summary work can still delay exit |
| save_memory | Empty key/value no longer reports successful storage | Reviewed; personal memory not changed by tests |
| recall_memory | Retained lookup; router selects it for saved personal facts | Live routing check only, no private facts queried |
| undo | Retained existing reversible-action journal | Reviewed; undo coverage depends on the originating action |
| browser_control | Cancel timed-out coroutine; added missing form-fields schema; flight navigation reuses an automation session | Schema check; authenticated websites not exercised |
| code_helper | Nonzero exit codes are reported; optional intent classifier capped at 16 tokens/15 seconds | Reviewed; generated code remains model-dependent |
| computer_control | Negative waits bounded at zero | Reviewed; actual clicks/typing not executed |
| computer_settings | Modern Windows endpoint support, scalar volume values, clamped targets; failure no longer becomes fake success | Mocked volume failure; hardware settings not changed |
| desktop_control | Unknown actions no longer silently generate and execute code | Regression test; explicit task mode remains model-generated code |
| dev_agent | Generated paths confined to project; quoted run arguments supported; nonzero exits/timeouts count as failures | Path and failure tests; dependency installation and full generated projects not exercised |
| file_controller | Bounded largest-file scan with bounded result storage; partial scans identified | Reviewed; no broad scan or personal file mutation |
| file_processor | Correct Python interpreter; execution exit status; media subprocess failures checked; archive preflight and overwrite rejection | Temporary archive and mocked media-failure tests |
| flight_finder | Reject invalid/ambiguous dates, removed stale encoded itinerary and fixed five-second wait; one browser session; no unsupported cheapest claim | Date/URL tests; page extraction remains best-effort and fares require verification |
| game_updater | Explicit action required; update requests no longer imply completed installation | Schema/review only; no game installation or shutdown |
| open_app | Existing launch failure reporting retained | Reviewed; no applications launched |
| reminder | Unique IDs prevent same-minute reminders overwriting each other | Reviewed; no tasks scheduled |
| send_message | Failed browser open reported; desktop send attempts described as unverified | Reviewed; no messages sent; recipient/delivery verification still needs a better integration |
| weather_report | Existing direct Open-Meteo retrieval retained; no browser needed | Four weather regressions and live check |
| web_search | Source retrieval without nested model calls; bounded result sizes and parallel comparisons | Mocked no-extra-model test and live source retrieval |
| youtube_video | Current transcript API supported; provided URL used without an unnecessary dialog | Reviewed; transcripts can be absent or blocked by YouTube |

All tools benefit from compact routing and shared argument validation. This is not a claim that every action of every tool has been exercised against every external app. GUI automation, messaging delivery, game launchers, hardware controls, and flight scraping remain dependent on external state. The speech-library deprecation warnings are separate from the model prompt delay and are not suppressed by this change.

Archive extraction refuses links, overwrites, more than 10,000 members, or over 1 GiB declared uncompressed content. Generated filenames cannot escape their project directory. These checks do not sandbox execution of generated code.

## Recommended additions, in priority order

1. **Calculator, units, dates, and time zones.** Deterministic local operations avoid model arithmetic and unnecessary search. Use exact decimal arithmetic for money-like calculations, with explicit units/time zones.
2. **Structured fact lookup.** Prefer an authoritative data API over snippets for supported topics. For example, [PokéAPI](https://pokeapi.co/docs/v2) supplies Pokémon types directly. Cache stable facts; retain the source and retrieval date. This would be a new structured capability, not another generic search tool.
3. **Home-server and Ollama diagnostics.** Read server availability, loaded model, memory pressure, and inference timings. Current `system_status` checks the Windows client, not the home inference server. Keep control/restart separate from read-only diagnostics.
4. **Indexed document search.** Search across local documents with citations and filenames instead of opening one file at a time. [SQLite FTS5](https://www.sqlite.org/fts5.html) offers a local full-text index; update it when files change instead of rescanning every question.
5. **Calendar and task-list integration.** Read upcoming events, check conflicts, and create requested events using a calendar provider's API. Existing reminders are notifications, not a calendar or task database.
6. **Git/GitHub project operations.** Repository status, diffs, branches, commits, and pull requests using Git and the [GitHub API](https://docs.github.com/en/rest). Existing code-writing tools do not provide a dedicated version-control workflow.
7. **Home Assistant integration.** Read device states and perform requested device actions through the [Home Assistant API](https://www.home-assistant.io/integrations/api/). Report the resulting device state rather than merely saying a command was sent.

Also worth improving, rather than counting as new tools: replace blind messaging keystrokes with a supported messaging API or verified UI automation, and verify browser/desktop outcomes before reporting completion. Keep the capability catalog small and load detailed schemas only when needed.
