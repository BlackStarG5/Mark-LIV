"""Small shared helpers for local, measurable agent operations."""
import json
from datetime import datetime, timezone
from pathlib import Path


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def result(**values):
    return json.dumps({'observed_at': stamp(), **values}, ensure_ascii=False, default=str)


def workspace(root):
    if not root:
        raise ValueError('An explicit project/root directory is required.')
    path = Path(root).expanduser().resolve()
    if not path.is_dir():
        raise ValueError('Root directory does not exist.')
    return path


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Path escapes the selected project directory.')
    return path


SKIP_DIRS = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.cache', '.tmp', 'logs'}
TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.csv', '.html', '.css', '.toml', '.yaml', '.yml', '.ini', '.rst'}


def is_link(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def searchable(path):
    return (not is_link(path) and path.name.lower() not in {'api_keys.json', 'credentials.json', 'id_rsa', 'id_ed25519'}
            and not path.name.lower().startswith('.env') and path.suffix.lower() in TEXT_EXTENSIONS)
