# Local chats and projects

The default Regular chat and all new conversations are saved on this PC under `Documents/Jarvis`. The Chats & projects panel on the right provides recents, New chat, and New project. New chats take their title from the first user message. Select a project heading and press New chat to create another chat in that project.

Use Attach beside Send to select one or more files. Add your question, then Send. Selecting a file never submits a request by itself. Clear files removes the pending attachments. If JARVIS is disconnected or asleep, the draft stays in the input. The Files tab lists copied, saved media; double-click an item to attach it to another message. Keep drafts in their current chat until sent or cleared.

Regular chats share the media library. A work project offers two context policies at creation:

- **Project only:** conversation retrieval, media, notes, tasks and tool history stay within that project. Global memory is excluded. Other chats cannot retrieve this project's conversations or media.
- **Shared:** the project can retrieve regular/shared conversations and media. Its conversations are also available to other shared chats. Private projects remain excluded.

Project folders live in `Documents/Jarvis/Projects/<name>-<id>`. The SQLite archive is `Documents/Jarvis/library.db`. Shared uploaded copies live in `Documents/Jarvis/Media`; project-only copies and state live inside their project folder. Original source files are not moved. Back up the entire Jarvis folder to retain conversations and uploads. Existing regular notes/tasks remain in the application's original local stores.

Project-only is an application context boundary, not an operating-system sandbox. JARVIS's general desktop/file/command tools still have the Windows account's access. It is not a security boundary for hostile documents or arbitrary generated code. There is no cloud sync, automatic model training, or guarantee of ChatGPT-level reasoning. Old conversations from before this archive existed cannot be recovered automatically.

Chat switching waits until the current response finishes or is interrupted. Responses and tool evidence are saved locally; the model still uses a bounded recent context and can search the saved archive with chat_library. The reactive center, face toggle, notes, tasks and activity console are retained.


New chats are drafts held in memory until their first user message; startup greetings do not create saved conversations. Titles use the beginning of the first message (no extra model call). Recents lists standalone chats; project chats appear once, under their project. Select a chat or project and use Delete selected to remove its saved conversations locally. A confirmation identifies the deletion scope. Project folders/files and shared media are preserved. Busy conversations or unsent drafts must finish or be cleared before deleting the active chat/project.
