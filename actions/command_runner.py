"""Bounded subprocess jobs with explicit working directories and retained output."""
import os
import subprocess
import sys
import threading
import time
import uuid
import psutil
from core.agent_support import result, workspace

_jobs = {}
_lock = threading.RLock()


async def await_result(raw, wait_seconds=20):
    """Bounded application follow-through; no model calls or command retries."""
    import asyncio
    import json
    deadline = time.monotonic() + wait_seconds
    while True:
        data = json.loads(raw)
        if data.get('status') != 'running' or time.monotonic() >= deadline:
            return raw
        await asyncio.sleep(.1)
        raw = await asyncio.to_thread(command_runner, {'action': 'poll', 'job_id': data['job_id']})


def stop_tree(process):
    try:
        parent = psutil.Process(process.pid)
        for child in reversed(parent.children(recursive=True)):
            try:
                child.kill()
            except psutil.Error:
                pass
        parent.kill()
    except psutil.Error:
        pass


def _collect(job):
    def read():
        try:
            while True:
                chunk = job['process'].stdout.read(1024)
                if not chunk:
                    break
                with _lock:
                    job['bytes_seen'] += len(chunk)
                    job['output'] = (job['output'] + chunk)[-16000:]
        finally:
            job['process'].stdout.close()
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        job['process'].wait(timeout=job['timeout'])
    except subprocess.TimeoutExpired:
        with _lock:
            job['timed_out'] = True
        stop_tree(job['process'])
        job['process'].wait(timeout=5)
    finally:
        reader.join(timeout=1)
        with _lock:
            job['finished'] = True


def command_runner(parameters):
    action = parameters['action']
    with _lock:
        if action == 'start':
            if sum(not j['finished'] for j in _jobs.values()) >= 4:
                return result(ok=False, error='Four jobs are already running. Poll or stop an existing job.')
            for key in list(_jobs):
                if len(_jobs) >= 24 and _jobs[key]['finished']:
                    del _jobs[key]
            root = workspace(parameters.get('root'))
            argv = parameters.get('argv')
            if not isinstance(argv, list) or not argv or len(argv) > 64 or not all(isinstance(a, str) and '\0' not in a for a in argv):
                raise ValueError('argv must be a nonempty list of executable and argument strings.')
            argv = list(argv)
            if argv[0].lower() in ('python', 'python3'):
                argv[0] = sys.executable
            process = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            job_id = uuid.uuid4().hex[:12]
            job = {'process': process, 'root': str(root), 'argv': argv, 'output': b'', 'bytes_seen': 0,
                   'timeout': max(1, min(300, int(parameters.get('timeout_seconds', 60)))), 'timed_out': False, 'cancelled': False, 'finished': False}
            _jobs[job_id] = job
            threading.Thread(target=_collect, args=(job,), daemon=True).start()
        elif action in ('poll', 'stop'):
            job_id = parameters.get('job_id')
            if job_id not in _jobs:
                return result(ok=False, error='Unknown job ID; jobs are retained only in this application session.')
            job = _jobs[job_id]
            if action == 'stop' and not job['finished']:
                job['cancelled'] = True
                stop_tree(job['process'])
        else:
            raise ValueError('Choose start, poll or stop.')
    # A short wait catches ordinary commands without an unnecessary extra poll.
    if action == 'start':
        until = time.monotonic() + .2
        while not job['finished'] and time.monotonic() < until:
            time.sleep(.01)
    with _lock:
        code = job['process'].poll()
        return result(ok=code == 0 and job['finished'] and not job['cancelled'] and not job['timed_out'], job_id=job_id,
                      status='finished' if job['finished'] else 'running', exit_code=code, timed_out=job['timed_out'], cancelled=job['cancelled'],
                      output=job['output'].decode('utf-8', errors='replace'), output_truncated=job['bytes_seen'] > 16000,
                      note='A running job is not complete. Exit code 0 verifies command exit, not correctness of the requested outcome.')


TOOL = {'name': 'command_runner', 'description': 'Run a requested command/test in an explicit project directory; retain job ID, output and exit code for poll/stop. argv is an argument array, not a shell string. Uses JARVIS Python for python. No interactive stdin. This is real local execution, not a sandbox; only run work the user requested.',
        'parameters': {'type': 'OBJECT', 'properties': {'action': {'type': 'STRING', 'enum': ['start', 'poll', 'stop']}, 'root': {'type': 'STRING'}, 'argv': {'type': 'ARRAY', 'items': {'type': 'STRING'}}, 'job_id': {'type': 'STRING'}, 'timeout_seconds': {'type': 'INTEGER'}}, 'required': ['action']}, 'handler': command_runner}
