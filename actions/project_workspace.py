"""Inspect and make exact, conflict-checked edits within an explicit project."""
import hashlib
import os
import tempfile
import time
import threading
from collections import OrderedDict
from core.agent_support import inside, result, searchable, SKIP_DIRS, workspace, is_link

_reads = OrderedDict()
_read_lock = threading.Lock()


def project_workspace(parameters):
    root = workspace(parameters.get('root'))
    action = parameters['action']
    if action in ('read', 'patch'):
        path = inside(root, parameters['path'])
        if path.stat().st_size > 2_000_000:
            raise ValueError('File exceeds the 2 MB editing limit.')
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        text = raw.decode('utf-8')
        if action == 'read':
            with _read_lock:
                _reads[str(path)] = digest
                _reads.move_to_end(str(path))
                if len(_reads) > 128:
                    _reads.popitem(last=False)
            start = max(1, int(parameters.get('line', 1)))
            lines = text.splitlines()
            return result(ok=True, path=str(path), sha256=digest, total_lines=len(lines),
                          content='\n'.join(f'{i+start}: {s}' for i, s in enumerate(lines[start-1:start+199]))[:20000])
        with _read_lock:
            expected = parameters.get('expected_sha256') or _reads.get(str(path))
        if not expected:
            return result(ok=False, error='Read this file with project_workspace before patching it.')
        if expected != digest:
            return result(ok=False, error='File changed since the last read. Read it again before editing.')
        old = parameters.get('old_text', '')
        new = parameters.get('new_text', '')
        if not old or text.count(old) != 1:
            return result(ok=False, error='old_text must match exactly once. No edit made.')
        updated = text.replace(old, new, 1).encode('utf-8')
        if len(updated) > 2_000_000:
            raise ValueError('Edited file exceeds 2 MB.')
        fd, temp = tempfile.mkstemp(dir=root, prefix='.jarvis-edit-')
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(updated)
            if path.read_bytes() != raw:
                return result(ok=False, error='Concurrent edit detected. Nothing replaced.')
            os.replace(temp, path)
            with _read_lock:
                _reads.pop(str(path), None)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        from core.undo import push_undo
        def undo():
            if path.read_bytes() != updated:
                raise RuntimeError('File changed after the patch; nothing undone.')
            path.write_bytes(raw)
            return 'Patch undone.'
        push_undo(f'patched {path.name}', undo)
        verified = path.read_bytes() == updated
        return result(ok=verified, path=str(path), verified=verified, sha256=hashlib.sha256(updated).hexdigest())
    if action not in ('list', 'search'):
        raise ValueError('Choose list, read, search or patch.')
    query = parameters.get('query', '')
    if action == 'search' and not query:
        raise ValueError('A literal search query is required.')
    output, scanned, partial = [], 0, False
    started = time.monotonic()
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not is_link(root / folder / d)]
        for name in files:
            scanned += 1
            if scanned > 3000 or time.monotonic()-started > 5 or len(output) >= 50:
                partial = True
                break
            path = inside(root, os.path.join(folder, name))
            if not searchable(path):
                continue
            if action == 'list':
                output.append({'path': str(path.relative_to(root))})
            elif path.stat().st_size <= 1_000_000:
                try:
                    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                        if query.casefold() in line.casefold():
                            output.append({'path': str(path.relative_to(root)), 'line': number, 'text': line[:500]})
                            if len(output) >= 50:
                                break
                except (UnicodeError, OSError):
                    continue
        if partial:
            break
    return result(ok=True, root=str(root), results=output, partial=partial, scanned_entries=scanned,
                  scope='Supported text/source files; dependencies and common credential files excluded.')


TOOL = {'name': 'project_workspace', 'description': 'Inspect a project: list, search literal content, read numbered lines, or patch one exact old_text/new_text match. Always read before patch: the tool remembers that version and rejects stale edits automatically. Saved bytes verified; undo supported.',
        'parameters': {'type': 'OBJECT', 'properties': {'root': {'type': 'STRING'}, 'action': {'type': 'STRING', 'enum': ['list', 'read', 'search', 'patch']}, 'path': {'type': 'STRING'}, 'query': {'type': 'STRING'}, 'line': {'type': 'INTEGER'}, 'expected_sha256': {'type': 'STRING'}, 'old_text': {'type': 'STRING'}, 'new_text': {'type': 'STRING'}}, 'required': ['root', 'action']}, 'handler': project_workspace}
