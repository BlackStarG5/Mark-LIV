# JARVIS agent upgrade

Restart JARVIS to load the new tools and prompt. The existing HUD, GPU Kokoro
voice, home Ollama model, and previous tools are retained.

## What changed

JARVIS now has 33 tool definitions: the existing 24 plus these nine additions.

| Tool | Capability | Important boundary |
|---|---|---|
| environment_inspect | Current JARVIS process RAM/CPU, PC readings, observed speech device, loaded Ollama models | Process RAM and PC RAM are separate. Ollama does not supply whole-server CPU/RAM. PyTorch GPU memory excludes driver overhead. |
| calculator | Bounded arithmetic, units, ISO dates/time zones | Floating-point approximations, not exact financial arithmetic. Explicit date offsets avoid daylight-saving ambiguity. |
| project_workspace | List/search source, numbered reads, exact patches and readback | Explicit root. Must read before patching; the tool remembers that version and rejects changes made since. Undo refuses to overwrite later changes. |
| command_runner | Run a command/test, retain its output, poll or stop a job | Real local execution, not a sandbox. Four concurrent jobs, 300-second maximum, last 16 KB of output retained. Jobs do not survive app restart. |
| git_project | Status, diffs, log, branches, explicit-file commits, fetch, fast-forward pull, push, draft PRs | No force/reset/clean/delete actions. Remote writes must be requested. PRs require GitHub CLI authentication. |
| document_search | Local text/PDF/DOCX indexing and cited full-text search | Explicit folder/index refresh. No OCR or semantic search. Stale matches omitted. Index size/time limits are reported. |
| task_history | Inspect actual tool-result records | Not an automatic proof that every part of a task was fulfilled. Legacy text results are labelled as reported results. |
| task_list | Persistent local to-dos, due dates, complete/reopen | Separate from calendar events and timed reminder notifications. Completion is a user-requested list status. |
| outlook_calendar | Outlook event/conflict lookup, personal event creation with readback, offline ICS drafts | Direct calendar access needs Microsoft setup/sign-in. Draft files are not saved calendar events. No invitation sending. |

Browser control also has an `inspect` action returning the current URL, page title,
visible text and controls. Interactive changes return observed page state, rather
than treating a click as proof that the entire task succeeded. Input values are
not included in the control inventory. Browser behavior still depends on websites;
the new inspection method is covered by mocked tests, not an authenticated-site audit.

Memory corrections retain an update timestamp, origin and previous value. The
current value continues to be what reaches the normal memory prompt.

## Conversation, speed and personality

- Hardware alerts and topic updates go to the status log, never the user-request
  queue. High GPU utilisation alone no longer generates alerts: games and inference
  routinely use the GPU heavily.
- Unsolicited conversational check-ins are off by default. The optional local
  `proactive_conversation_enabled` setting enables the legacy feature; it waits
  for the request queue and active turn to be idle.
- Fully matched simple arithmetic and application-RAM questions call the tools
  directly, without router/answer inference. More complex wording uses normal
  tool selection. Multi-step requests never use these shortcuts.
- Late results from interrupted tool calls cannot release or populate a newer
  request; any associated old screen capture is discarded.
- Short command jobs are followed for up to 20 seconds without model polling.
  Longer jobs return an explicit unfinished status and ID; ask to check that job.
  JARVIS does not promise an unattended follow-up it has not scheduled.
- The prompt uses composed, concise language and occasional dry British humour.
  It discourages repeated “sir,” canned offers, invented measurements and false
  success claims. Both the default compact prompt and optional legacy prompt were
  updated. This changes personality, not the voice model or a cloned actor voice.

## Try these

1. “What's the square root of pi?”
2. “How much RAM are you currently using out of my 64GB?”
3. “Inspect your speech device and the home Ollama server.”
4. “In project C:/path/to/project, read the relevant source, fix this bug, and run
   its tests. Use project_workspace and command_runner. Report the actual result.”
5. “Index C:/path/to/documents, then search those documents for roof warranty.
   Show the matching filenames and passages.”
6. “Add test JARVIS calendar to my task list, due 2026-10-01.”
7. “Show the recent tool history. Which commands failed or are still running?”

Use the actual project/document path. The example task date is explicit; choose
your intended date instead. Document indexes and tool-outcome logs stay local and
are ignored by Git. Logs can contain result excerpts; they are not uploaded by
the logging feature. Tool results selected for conversation go to the configured
home Ollama server, as before.

## GitHub connection

A checksum-verified portable GitHub CLI is installed at `.tools/gh.exe` on this
PC. Local Git operations use the existing Git installation. The new CLI currently
has no signed-in account; PR operations will report that rather than invent success.
For a fresh checkout, install GitHub CLI or place its official executable there.

From the installed project directory, run:

```powershell
.\.tools\gh.exe auth login --hostname github.com --git-protocol https --web
```

Complete sign-in yourself in the browser. Never paste passwords or tokens into
JARVIS. Git commits/pushes and PR creation are only appropriate when requested.

## Windows/Outlook calendar connection

This PC has `Microsoft.OutlookForWindows` installed. Microsoft replaced the older
Windows Mail/Calendar apps with Outlook. Merely having Outlook installed does not
grant another application calendar access.

Offline event drafting works without an account: ask for an Outlook calendar
draft with a title and explicit start/end time and timezone. It writes an `.ics`
file under Documents/JARVIS Calendar Drafts. Open/import it in Outlook yourself;
JARVIS reports that it is a draft, not an added calendar event.

For direct event reads/writes, one-time setup remains:

1. Register a personal Microsoft public-client application in Microsoft Entra.
   Choose supported accounts including personal Microsoft accounts if using
   Outlook.com. Add a **Mobile and desktop applications** redirect URI of
   `http://localhost` and delegated Microsoft Graph `Calendars.ReadWrite` permission.
   No client secret is required for this desktop flow. Organisational policy may
   require administrator consent or restrict registration.
2. Run the included connector with that application's non-secret client ID:

   ```powershell
   .\.venv\Scripts\python.exe connect_outlook.py --client-id YOUR-APPLICATION-ID
   ```

3. Sign in and grant calendar access in Microsoft's browser window. Passwords
   never enter JARVIS. The token cache is protected by Windows DPAPI for your
   Windows account and excluded from Git.

The connector targets Microsoft calendars, not a Gmail calendar merely displayed
inside Outlook. No account registration, consent or live calendar changes were
performed during development. Those account-dependent operations are not yet
live-verified. Local tasks and drafts work independently.

## Validation and remaining limits

86 automated tests pass, and all 33 tool parameter schemas validate.

The live Qwen3:8B test read a disposable broken Python project, patched subtraction
into addition, ran a unit test and correctly reported its success. The successful
run took about 32 seconds; multiple server inference calls still dominate this
kind of work. The first two attempts exposed omitted hash arguments and premature
completion after starting a job; both prompted tool/orchestration corrections.

The direct square-root answer took about 6–7 ms and process-RAM inspection about
126–127 ms in that test, excluding microphone and speech generation. The reported
process was the test application's process, not a measurement of your running GUI.
The home Ollama endpoint also returned its loaded Qwen3:8B model successfully.

Tests exercise calculations, invalid expressions, process-vs-PC scope, exact and
stale patches, document indexing, failed/timed-out commands, Git commit isolation,
background alert isolation, calendar drafts and connection failures. They do not
establish frontier-model reasoning parity or reliability on every external app.
Messaging delivery, flight scraping and game-launcher automation retain their
previous external-state limitations. No claims of guaranteed accuracy or gaming
FPS improvements are made.

Implementation references:
- https://docs.ollama.com/api/ps
- https://cli.github.com/manual/gh_pr_create
- https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/user-post-events?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens


## Desktop partner capabilities (September 26 update)

- CPU investigations route directly to live process sampling and show measured
  average/peak busy time. They cannot reconstruct an earlier spike. Collection
  overhead is included in the reported duration; sampling is not a historical monitor.
- `desktop_inspect` reads titled windows/PIDs, active window, monitor geometry,
  and largest resident-memory processes. Existing screen and computer-control
  tools handle visual inspection and interaction.
- `gpu_diagnostics` reads NVIDIA driver telemetry, including utilization,
  VRAM, temperature, power and performance state. It does not prove hardware health.
- `malware_scan` starts a Defender custom scan of an explicit absolute path and
  retains output/job status. Remediation is disabled; a scan is not a whole-PC
  malware guarantee. Permission failures and the five-minute job limit are reported.
- `developer_environment` discovers Java/build tools and IntelliJ; it can request
  opening a specified project in IntelliJ. Project creation refuses overwrite,
  exact patches require prior reads, and command execution supplies build output.
- Coding requests select a build workflow, rather than the game installer.
  Minecraft version and loader must be established; source generation alone is
  not a verified mod. Minecraft builds and IntelliJ interaction have not been
  validated end to end in this update.
- Build/scan jobs receive up to five minutes of automatic result checking,
  without repeated model polling. An interrupted or timed-out job is not success.

Useful requests: “Investigate my CPU spikes”; “Check my GPU”; “Inspect my
 desktop environment”; “Scan C:\specific\folder for malware”; or “Build a
Minecraft mod for [version] using [loader] in [project folder], build it and
open it in IntelliJ.”

Defender command reference:
https://learn.microsoft.com/en-us/defender-endpoint/command-line-arguments-microsoft-defender-antivirus
