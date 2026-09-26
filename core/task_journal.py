"""Bounded local record of actual tool outcomes, separate from model claims."""
import json
from pathlib import Path
import threading
from core.agent_support import stamp

PATH = Path(__file__).resolve().parent.parent / 'logs' / 'tool-outcomes.jsonl'
_lock = threading.Lock()


def record(tool, output):
    text = str(output)
    state = 'reported_result'
    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get('ok'), bool):
            state = 'running' if data.get('status') == 'running' else 'succeeded' if data['ok'] else 'failed'
    except (ValueError, TypeError):
        if 'CONFIRMATION_PENDING' in text:
            state = 'awaiting_confirmation'
        elif text.startswith(('Tool ', 'Could not ', 'File already exists:', 'Not executed:', 'Access denied:')):
            state = 'blocked_or_failed'
    entry = {'at': stamp(), 'tool': tool, 'state': state, 'result_excerpt': text[:1500]}
    try:
        with _lock:
            PATH.parent.mkdir(parents=True, exist_ok=True)
            if PATH.exists() and PATH.stat().st_size > 1_000_000:
                PATH.write_text('\n'.join(PATH.read_text(encoding='utf-8').splitlines()[-100:])+'\n', encoding='utf-8')
            with PATH.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(entry, ensure_ascii=False)+'\n')
    except OSError:
        pass  # A journal failure must never cause an action to be retried.


def recent(limit=10):
    with _lock:
        if not PATH.exists():
            return []
        lines = PATH.read_text(encoding='utf-8').splitlines()[-max(1, min(30, limit)):]
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries
