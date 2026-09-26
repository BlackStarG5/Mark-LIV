import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from actions.calculator import calculate, evaluate
from actions.command_runner import command_runner
from actions.document_search import document_search
from actions.environment_inspect import inspect_environment
from actions.git_project import git_project
from actions.project_workspace import project_workspace
from core.direct_requests import direct_request


class MathTests(unittest.TestCase):
    def test_real_arithmetic(self):
        self.assertAlmostEqual(evaluate('sqrt(pi)'), math.sqrt(math.pi))
        self.assertEqual(evaluate('(2+3)*4'), 20)
        self.assertAlmostEqual(json.loads(calculate({'operation': 'convert', 'value': 32, 'from_unit': 'f', 'to_unit': 'c'}))['value'], 0)

    def test_reject_code_and_excessive_calculation(self):
        for expression in ('__import__("os").getcwd()', '[1]*100000', '2**10000000', '9**(9**9)', 'sqrt(-1)', '1/0'):
            with self.subTest(expression=expression), self.assertRaises((ValueError, ZeroDivisionError)):
                evaluate(expression)

    def test_units_do_not_mix_quantities(self):
        with self.assertRaises(ValueError):
            calculate({'operation': 'convert', 'value': 1, 'from_unit': 'kg', 'to_unit': 'm'})

    def test_timezone_and_ambiguous_dates(self):
        actual = json.loads(calculate({'operation': 'date', 'datetime': '2026-01-01T12:00:00+00:00', 'timezone': 'America/New_York'}))
        self.assertEqual(actual['value'], '2026-01-01T07:00:00-05:00')
        with self.assertRaises(ValueError):
            calculate({'operation': 'date', 'datetime': '2026-11-01T01:30:00', 'timezone': 'America/New_York'})

    def test_direct_requests_are_complete_matches(self):
        self.assertEqual(direct_request("What's the square root of pi?")[0], 'calculator')
        self.assertEqual(direct_request('Hey, how much RAM are you currently using out of my 64GB?')[1], {'scope': 'app'})
        self.assertIsNone(direct_request('Calculate 2+2 and save it in a file'))
        self.assertIsNone(direct_request('How much memory is my server using?'))


class EnvironmentTests(unittest.TestCase):
    def test_app_uses_current_process_not_whole_machine(self):
        fake = Mock()
        fake.pid = 123
        fake.memory_info.return_value = NS(rss=2**30)
        fake.children.return_value = []
        fake.cpu_percent.return_value = 5
        fake.create_time.return_value = time.time()-10
        with patch('actions.environment_inspect.psutil.Process', return_value=fake) as process, patch('actions.system_monitor.get_system_status') as system:
            data = json.loads(inspect_environment({'scope': 'app'}))
        process.assert_called_once_with(os.getpid())
        system.assert_not_called()
        self.assertEqual(data['app']['rss_gib'], 1)
        self.assertNotIn('pc', data)

    def test_server_failure_does_not_invent_measurement(self):
        import requests
        with patch('actions.environment_inspect.requests.get', side_effect=requests.Timeout):
            data = json.loads(inspect_environment({'scope': 'server'}))
        self.assertFalse(data['server']['reachable'])
        self.assertIn('Unavailable', data['server']['host_cpu_ram'])

    def test_high_gpu_load_alone_does_not_alert(self):
        from actions.system_monitor import SystemMonitor
        with patch('actions.system_monitor.psutil.cpu_percent', return_value=20), patch('actions.system_monitor.psutil.virtual_memory', return_value=NS(percent=40)), patch('actions.system_monitor._get_cpu_temp', return_value=45), patch('actions.system_monitor._get_gpu_usage', return_value=100):
            self.assertIsNone(SystemMonitor().check())


class ProjectTests(unittest.TestCase):
    def test_automatic_read_version_rejects_later_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder, 'test.txt'); target.write_text('before')
            read = {'root': folder, 'action': 'read', 'path': 'test.txt'}
            args = {'root': folder, 'action': 'patch', 'path': 'test.txt', 'old_text': 'before', 'new_text': 'after'}
            self.assertFalse(json.loads(project_workspace(args))['ok'])
            project_workspace(read)
            target.write_text('before changed externally')
            self.assertFalse(json.loads(project_workspace(args))['ok'])
            target.write_text('before'); project_workspace(read)
            self.assertTrue(json.loads(project_workspace(args))['verified'])

    def test_exact_patch_checks_hash_and_preserves_crlf(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder, 'test.txt')
            target.write_bytes(b'one\r\ntwo\r\n')
            args = {'root': folder, 'action': 'patch', 'path': 'test.txt', 'old_text': 'two', 'new_text': 'three', 'expected_sha256': 'wrong'}
            self.assertFalse(json.loads(project_workspace(args))['ok'])
            args['expected_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertTrue(json.loads(project_workspace(args))['verified'])
            self.assertEqual(target.read_bytes(), b'one\r\nthree\r\n')

    def test_ambiguous_patch_and_escape_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder, 'test.txt'); target.write_text('a a')
            args = {'root': folder, 'action': 'patch', 'path': 'test.txt', 'old_text': 'a', 'new_text': 'b', 'expected_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
            self.assertFalse(json.loads(project_workspace(args))['ok'])
            with self.assertRaises(ValueError):
                project_workspace({'root': folder, 'action': 'read', 'path': '../outside.txt'})

    def test_search_cites_line_and_skips_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'source.py').write_text('line\nneedle')
            Path(folder, 'api_keys.json').write_text('needle')
            data = json.loads(project_workspace({'root': folder, 'action': 'search', 'query': 'needle'}))
            self.assertEqual(data['results'], [{'path': 'source.py', 'line': 2, 'text': 'needle'}])

    def test_document_index_omits_stale_and_deleted_results(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as indexes, patch('actions.document_search.INDEX_DIR', Path(indexes)):
            target = Path(folder, 'notes.txt'); target.write_text('launch project alpha')
            index = {'root': folder, 'action': 'index'}
            search = {'root': folder, 'action': 'search', 'query': 'alpha'}
            document_search(index)
            self.assertEqual(json.loads(document_search(search))['matches'][0]['file'], str(target))
            target.write_text('different content now')
            self.assertEqual(json.loads(document_search(search))['matches'], [])
            target.unlink(); document_search(index)
            self.assertEqual(json.loads(document_search(search))['indexed_files'], 0)

    def test_git_commit_excludes_unrelated_staged_file(self):
        with tempfile.TemporaryDirectory() as folder:
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=folder, stderr=subprocess.STDOUT).decode()
            git('init'); git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.invalid')
            Path(folder, 'base.txt').write_text('base'); git('add', '.'); git('commit', '-m', 'base')
            Path(folder, 'ours.txt').write_text('ours'); Path(folder, 'other.txt').write_text('other'); git('add', 'other.txt')
            data = json.loads(git_project({'root': folder, 'action': 'commit', 'paths': ['ours.txt'], 'message': 'Only ours'}))
            self.assertTrue(data['ok'], data)
            self.assertEqual(git('show', '--pretty=', '--name-only', 'HEAD').strip(), 'ours.txt')
            self.assertIn('other.txt', git('diff', '--cached', '--name-only'))


class JobTests(unittest.TestCase):
    def finish(self, job):
        deadline = time.monotonic()+8
        while job['status'] != 'finished' and time.monotonic() < deadline:
            time.sleep(.05)
            job = json.loads(command_runner({'action': 'poll', 'job_id': job['job_id']}))
        self.assertEqual(job['status'], 'finished')
        return job

    def test_failed_command_retains_output_and_exit_code(self):
        with tempfile.TemporaryDirectory() as folder:
            data = self.finish(json.loads(command_runner({'action': 'start', 'root': folder, 'argv': ['python', '-c', 'import sys; print("failure evidence"); sys.exit(3)']})))
            self.assertFalse(data['ok']); self.assertEqual(data['exit_code'], 3)
            self.assertIn('failure evidence', data['output'])

    def test_timeout_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as folder:
            data = self.finish(json.loads(command_runner({'action': 'start', 'root': folder, 'timeout_seconds': 1, 'argv': ['python', '-c', 'import time; time.sleep(30)']})))
            self.assertFalse(data['ok']); self.assertTrue(data['timed_out'])


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_application_waits_for_command_exit_without_model_poll(self):
        from actions.command_runner import await_result
        with tempfile.TemporaryDirectory() as folder:
            raw = command_runner({'action': 'start', 'root': folder, 'argv': ['python', '-c', 'import time; time.sleep(.4); print("verified")']})
            data = json.loads(await await_result(raw, wait_seconds=5))
            self.assertTrue(data['ok'])
            self.assertIn('verified', data['output'])

    async def test_running_job_reply_does_not_promise_unattended_followup(self):
        from core.local_session import LocalSession
        declaration = {'name': 'command_runner', 'parameters': {'type': 'OBJECT', 'properties': {}}}
        session = LocalSession({'system_instruction': 'Test', 'declarations': [declaration]}, speech=NS(synthesize=lambda _: b''))
        call = {'tool_calls': [{'function': {'name': 'command_runner', 'arguments': {}}}]}
        with tempfile.TemporaryDirectory() as folder, patch('core.task_journal.PATH', Path(folder, 'log')), patch('core.home_llm.chat', return_value=call) as model:
            turn = asyncio.create_task(session._turn([{'text': 'Run a long test'}]))
            await session.events.get()
            session.tool_results = [NS(name='command_runner', response={'result': json.dumps({'status': 'running', 'job_id': 'example'})})]
            session.tool_done.set()
            await turn
            self.assertEqual(model.call_count, 1)
            self.assertIn('not verified', session.history[-1]['content'])

    async def test_browser_inspection_returns_observed_state(self):
        from actions.browser_control import _BrowserSession
        session = object.__new__(_BrowserSession)
        page = NS(url='https://example.invalid/result', title=AsyncMock(return_value='Result'),
                  inner_text=AsyncMock(return_value='Saved'), locator=Mock(return_value=NS(evaluate_all=AsyncMock(return_value=[{'tag': 'button', 'label': 'Done'}]))))
        session._get_page = AsyncMock(return_value=page)
        actual = json.loads(await session.inspect())
        self.assertEqual(actual['text'], 'Saved')
        self.assertEqual(actual['elements'][0]['label'], 'Done')

    async def test_direct_math_has_no_model_calls(self):
        from core.local_session import LocalSession
        from actions.calculator import TOOL
        with tempfile.TemporaryDirectory() as folder, patch('core.task_journal.PATH', Path(folder, 'journal.jsonl')), patch('core.home_llm.chat') as model:
            session = LocalSession({'system_instruction': 'Test', 'declarations': [TOOL], 'direct_requests': True}, speech=NS(synthesize=lambda _: b''))
            await session._turn([{'text': "What's the square root of pi?"}])
            model.assert_not_called()
            self.assertIn('1.77245385091', session.history[-1]['content'])

    async def test_monitor_never_injects_user_prompt(self):
        import main
        app = object.__new__(main.JarvisLive)
        app._sys_monitor = NS(check=lambda: 'Whole-PC RAM usage is 95%.')
        app.session = NS(send_client_content=AsyncMock())
        app._awake = True; app.ui = NS(write_log=Mock())
        with patch('main.asyncio.sleep', side_effect=[None, asyncio.CancelledError()]):
            with self.assertRaises(asyncio.CancelledError):
                await app._run_system_monitor()
        app.session.send_client_content.assert_not_called()
        app.ui.write_log.assert_called_once_with('SYS: Whole-PC RAM usage is 95%.')


class JournalTests(unittest.TestCase):
    def test_memory_correction_keeps_origin_and_previous_value(self):
        from memory.memory_manager import _recursive_update
        memory = {'name': {'value': 'Before'}}
        _recursive_update(memory, {'name': {'value': 'After', 'source': 'save_memory tool'}})
        self.assertEqual(memory['name']['value'], 'After')
        self.assertEqual(memory['name']['previous_value'], 'Before')
        self.assertEqual(memory['name']['source'], 'save_memory tool')

    def test_local_tasks_persist_and_do_not_duplicate(self):
        from actions.task_list import task_list
        with tempfile.TemporaryDirectory() as folder, patch('actions.task_list.PATH', Path(folder, 'tasks.db')):
            args = {'action': 'add', 'title': 'Test the assistant', 'due': '2026-10-01'}
            created = json.loads(task_list(args))
            self.assertEqual(json.loads(task_list(args))['id'], created['id'])
            self.assertEqual(len(json.loads(task_list({'action': 'list'}))['tasks']), 1)
            self.assertTrue(json.loads(task_list({'action': 'complete', 'id': created['id']}))['ok'])
            self.assertEqual(json.loads(task_list({'action': 'list'}))['tasks'], [])

    def test_running_result_is_not_completed(self):
        from core.task_journal import record, recent
        with tempfile.TemporaryDirectory() as folder, patch('core.task_journal.PATH', Path(folder, 'journal.jsonl')):
            record('command_runner', json.dumps({'ok': False, 'status': 'running'}))
            record('file_controller', 'File already exists: example.txt')
            self.assertEqual([e['state'] for e in recent()], ['running', 'blocked_or_failed'])


class CalendarTests(unittest.TestCase):
    def test_unconnected_calendar_is_not_reported_as_ready(self):
        from actions.outlook_calendar import outlook_calendar
        with patch('actions.outlook_calendar.token', return_value=None):
            self.assertFalse(json.loads(outlook_calendar({'action': 'status'}))['connected'])

    def test_ics_draft_does_not_claim_saved_and_escapes_lines(self):
        from actions.outlook_calendar import outlook_calendar
        with tempfile.TemporaryDirectory() as folder, patch('actions.outlook_calendar.DRAFTS', Path(folder)):
            data = json.loads(outlook_calendar({'action': 'draft', 'title': 'Test\nBEGIN:BAD', 'start': '2026-10-01T13:00:00-04:00', 'end': '2026-10-01T14:00:00-04:00'}))
            self.assertFalse(data['calendar_saved'])
            content = Path(data['draft_file']).read_bytes()
            self.assertIn(b'DTSTART:20261001T170000Z', content)
            self.assertNotIn(b'\r\nBEGIN:BAD', content)

    def test_calendar_rejects_ambiguous_time(self):
        from actions.outlook_calendar import interval
        with self.assertRaises(ValueError):
            interval({'start': '2026-11-01T01:00:00', 'end': '2026-11-01T02:00:00'})

    def test_creation_timeout_is_unknown_not_retryable_failure(self):
        from actions.outlook_calendar import outlook_calendar
        import requests
        with patch('actions.outlook_calendar.token', return_value='test-token'), patch('actions.outlook_calendar.requests.post', side_effect=requests.Timeout):
            data = json.loads(outlook_calendar({'action': 'create', 'title': 'Test', 'start': '2026-10-01T13:00:00-04:00', 'end': '2026-10-01T14:00:00-04:00'}))
            self.assertEqual(data['outcome'], 'unknown')
