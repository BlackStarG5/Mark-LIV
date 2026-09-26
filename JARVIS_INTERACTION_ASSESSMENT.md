# JARVIS live interaction assessment — 26 September 2026

Tested the actual home model through LocalSession, contextual routing, and native action handlers. Speech was disabled. File writes and Python execution were restricted to disposable trial folders. Desktop inspection was read-only. This tests the text/model/tool loop, not the live microphone, visual clicking, or every GUI app.

## Results

| Test | Result | Evidence |
|---|---|---|
| Natural-language file creation and verification | Failed | Omitted the filename in create_file, attempted to open the directory as a file, then misinterpreted the error as permission trouble. |
| Follow-up correction after that failure | Failed | Routed as conversation; promised an edit but made no tool call. |
| Code inspection request in that conversation | Failed | Promised inspection and execution without using tools. |
| Explain prior work | Failed grounding | Offered a speculative explanation instead of plainly stating no repair had happened. |
| Monitor count and active window | Partial | Correctly reported two monitors; requested only monitor information and did not follow through to inspect the active window. Added an unsupported statement that the desktop was stable. |
| Independent code repair in a fresh conversation | Failed repair | Read the file and ran its assertion. Correctly identified +1, but proposed -1 or changing the assertion, made no patch, and did not rerun. The correct implementation is sum(values). |
| Guided file creation with explicit tool fields | Passed | Created and read fruits.txt with the exact three requested lines. |
| Contextual edit after successful creation | Passed | Wrote and read back Apples / Grapes / Oranges. Independently checked the saved file. |

## What this establishes

JARVIS can execute local file tools, run a Python script, inspect monitor information, and use conversational references after a successful action. It is not yet reliable at independently selecting actions, recovering from argument errors, completing multi-step requests, or distinguishing intentions from completed work. The simple code-repair result also exposes a reasoning limitation; tool access alone cannot fix that.

The first trial had an overly restrictive harness that blocked file_controller. Its file/coding outcomes are excluded; the corrected v2 and independent v3 trials above permitted both file tools within their test folders. The later trial failures shown above were not caused by that boundary.

## Prioritized improvements

1. Detect when an action request was routed to conversation and the response merely promises work.
2. Validate required semantic arguments (directory plus filename) and return actionable errors.
3. Track requested steps and require evidence for each before stopping.
4. Retry a diagnosed argument mistake without inventing a permissions problem.
5. Verify code changes against unchanged tests; never present an unexecuted suggestion as a fix.
6. Test memory, GUI element targeting, browser forms, interruption, and longer projects separately.

No existing user files, settings, notes, or task lists were changed. Application code was not modified during this assessment. Raw trial records are retained in .tmp/interaction-results-v2.json and .tmp/interaction-results-v3.json; desktop records may contain window titles and are local only.


## Retest after reliability changes and local-chat work

- Natural file creation and contextual correction now passed, with the saved file independently checked as Apples / Grapes / Oranges.
- The independent repair initially failed on a fabricated directory segment and omitted required arguments. The application now rejects nonexistent project roots before execution and allows two bounded schema corrections.
- The final actual-home-model repair took 66.1 seconds. It read the implementation, ran the failing assertion, patched `sum(values) + 1` to `sum(values)`, and reran to exit 0 with TEST PASSED. The original assertion was independently checked unchanged. Several redundant reads and mistaken patch attempts occurred before the successful patch: this is a pass on the small task, not evidence of reliable large-project autonomy.
- Offscreen desktop UI tests passed attachment staging, prompt-plus-file submission, retained drafts while unavailable, file-copy persistence, restored chat history and private-project media filtering. Model/tool tests disabled speech; microphone, TTS and arbitrary GUI workflows were not retested.
- A fresh live timed-note test saved the apples note with 12 a.m. intact in 8.9 seconds, confirmed by reading the temporary notes database. A fresh desktop test retrieved both monitors and the active window in 41.1 seconds. These pass the tested requests; desktop inspection still made a redundant call.
