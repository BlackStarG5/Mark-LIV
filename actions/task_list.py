"""Persistent local personal tasks, independent of calendar/account services."""
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
import sqlite3
import uuid
from core.agent_support import result, stamp

PATH = Path(__file__).resolve().parent.parent / 'memory' / 'tasks.db'


def task_list(parameters):
    action = parameters['action']
    PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(PATH, timeout=5)) as conn, conn:
        conn.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, title TEXT, due TEXT, status TEXT, updated TEXT)')
        if action == 'add':
            title = parameters.get('title', '').strip()
            due = parameters.get('due', '').strip()
            if not title or len(title) > 500:
                raise ValueError('Task title must contain 1–500 characters.')
            if due:
                if len(due) == 10:
                    date.fromisoformat(due)
                elif datetime.fromisoformat(due).tzinfo is None:
                    raise ValueError('Timed due dates require an ISO timezone offset; an all-day YYYY-MM-DD date is also accepted.')
            existing = conn.execute("SELECT id FROM tasks WHERE title=? AND due=? AND status='open'", (title, due)).fetchone()
            if existing:
                return result(ok=True, id=existing[0], already_exists=True, note='An identical open task already exists; no duplicate added.')
            task_id = uuid.uuid4().hex[:12]
            conn.execute('INSERT INTO tasks VALUES (?,?,?,?,?)', (task_id, title, due, 'open', stamp()))
            return result(ok=True, id=task_id, title=title, due=due, status='open', note='Saved locally. This is not a calendar event or a scheduled notification.')
        if action in ('complete', 'reopen'):
            task_id = parameters.get('id', '')
            status = 'completed' if action == 'complete' else 'open'
            count = conn.execute('UPDATE tasks SET status=?, updated=? WHERE id=?', (status, stamp(), task_id)).rowcount
            return result(ok=bool(count), id=task_id, status=status if count else 'not_found', note='Task-list status set on request; not independent verification of the real-world task.')
        if action == 'list':
            rows = conn.execute("SELECT * FROM tasks WHERE status=? ORDER BY CASE WHEN due='' THEN 1 ELSE 0 END, due, updated DESC LIMIT 50", (parameters.get('status', 'open'),)).fetchall()
            return result(ok=True, tasks=[dict(zip(('id', 'title', 'due', 'status', 'updated'), row)) for row in rows], limit=50)
        raise ValueError('Choose add, list, complete or reopen.')


TOOL = {'name': 'task_list', 'description': 'Maintain a persistent local to-do list: add/list/complete/reopen tasks. Optional due date. Mark complete only when requested. Does not create calendar events or send notifications; use reminder for notifications.',
        'parameters': {'type': 'OBJECT', 'properties': {'action': {'type': 'STRING', 'enum': ['add', 'list', 'complete', 'reopen']}, 'title': {'type': 'STRING'}, 'due': {'type': 'STRING'}, 'id': {'type': 'STRING'}, 'status': {'type': 'STRING', 'enum': ['open', 'completed']}}, 'required': ['action']}, 'handler': task_list}
