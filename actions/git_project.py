"""Explicit Git and GitHub operations; no force push, reset, clean or deletion."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from core.agent_support import inside, result, workspace


def run(argv, root, timeout=30):
    if argv[0] == 'gh':
        binary = shutil.which('gh') or str(Path(__file__).resolve().parent.parent / '.tools' / 'gh.exe')
        if not Path(binary).is_file():
            return 1, 'GitHub CLI is unavailable. Install gh and sign in; local Git operations remain available.'
        argv = [binary, *argv[1:]]
    done = subprocess.run(argv, cwd=root, capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', timeout=timeout,
                          env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GH_PROMPT_DISABLED': '1'})
    return done.returncode, (done.stdout + done.stderr)[:14000]


def git_project(parameters):
    root = workspace(parameters.get('root'))
    code, top = run(['git', 'rev-parse', '--show-toplevel'], root)
    if code or Path(top.strip()).resolve() != root:
        return result(ok=False, error='root must be the exact Git repository top-level directory.')
    action = parameters['action']
    fixed = {'status': ['status', '--short', '--branch'], 'diff': ['diff', '--no-ext-diff', '--no-textconv', '--'],
             'staged_diff': ['diff', '--cached', '--no-ext-diff', '--no-textconv', '--'], 'log': ['log', '-8', '--oneline'], 'branches': ['branch', '--list'],
             'fetch': ['fetch', 'origin'], 'pull': ['pull', '--ff-only', 'origin'], 'push': ['push', '--set-upstream', 'origin', 'HEAD']}
    if action in fixed:
        code, output = run(['git', *fixed[action]], root)
    elif action in ('branch', 'switch'):
        branch = parameters.get('branch', '')
        valid, _ = run(['git', 'check-ref-format', '--branch', branch], root)
        if valid or branch.startswith('-') or not branch:
            raise ValueError('Invalid branch name.')
        code, output = run(['git', 'switch', *(['-c'] if action == 'branch' else []), branch], root)
    elif action == 'commit':
        paths, message = parameters.get('paths', []), parameters.get('message', '')
        if not paths or not message.strip():
            raise ValueError('Commit requires explicit file paths and a message.')
        if any(not p or Path(p).is_absolute() or p.startswith(':') for p in paths):
            raise ValueError('Commit paths must be literal relative file paths.')
        for p in paths:
            target = inside(root, p)
            if target.is_dir():
                raise ValueError('List individual files, not directories.')
        code, output = run(['git', '--literal-pathspecs', 'add', '--', *paths], root)
        if code == 0:
            # --only does not include unrelated staged changes in this commit.
            code, output = run(['git', '--literal-pathspecs', 'commit', '--only', '-m', message, '--', *paths], root)
    elif action == 'pr_list':
        code, output = run(['gh', 'pr', 'list', '--json', 'number,title,url,state,headRefName'], root)
    elif action == 'pr_create':
        title, body = parameters.get('title', ''), parameters.get('body', '')
        if not title.strip() or not body.strip():
            raise ValueError('Provide a PR title and reviewable description.')
        code, upstream = run(['git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], root)
        if code:
            return result(ok=False, error='Push this branch and configure its upstream before creating a PR. No implicit push or fork performed.')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'body.md'
            path.write_text(body, encoding='utf-8')
            args = ['gh', 'pr', 'create', '--draft', '--title', title, '--body-file', str(path)]
            if parameters.get('base'):
                args += ['--base', parameters['base']]
            code, output = run(args, root)
    else:
        raise ValueError('Unsupported Git operation.')
    return result(ok=code == 0, action=action, exit_code=code, output=output,
                  note='Remote writes require user instruction. GitHub operations require installed, signed-in gh. No credentials are requested by this tool.')


TOOL = {'name': 'git_project', 'description': 'Git status/diff/log/branches, create or switch branch, commit explicit files, fetch/pull fast-forward, push, list or create draft GitHub PR. Only commit/push/create PR when requested. Existing gh authentication required for PRs.',
        'parameters': {'type': 'OBJECT', 'properties': {'root': {'type': 'STRING'}, 'action': {'type': 'STRING', 'enum': ['status', 'diff', 'staged_diff', 'log', 'branches', 'branch', 'switch', 'commit', 'fetch', 'pull', 'push', 'pr_list', 'pr_create']}, 'branch': {'type': 'STRING'}, 'paths': {'type': 'ARRAY', 'items': {'type': 'STRING'}}, 'message': {'type': 'STRING'}, 'title': {'type': 'STRING'}, 'body': {'type': 'STRING'}, 'base': {'type': 'STRING'}}, 'required': ['root', 'action']}, 'handler': git_project}
