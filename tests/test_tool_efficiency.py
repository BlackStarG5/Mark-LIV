import asyncio
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from core import home_llm
from core.file_safety import child_path, extract_archive
from core.tool_catalog import select_tools
from core.local_session import LocalSession
from core.action_loader import ActionRecord, ActionRegistry

DECLARATIONS = [{'name': 'weather_report', 'description': 'Read weather.',
                 'parameters': {'type': 'OBJECT', 'properties': {'city': {'type': 'STRING'}}, 'required': ['city']}}]


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    def test_router_cannot_supply_unverified_shortcut_answer(self):
        with patch.object(home_llm, 'chat', return_value={'content': '{"tools":[],"answer":"untrusted shortcut"}'}) as chat:
            selected = select_tools('What type is Incineroar?', [], DECLARATIONS)
        self.assertEqual(selected, set())
        self.assertFalse(chat.call_args.kwargs['think'])
        self.assertLessEqual(chat.call_args.kwargs['max_tokens'], 64)
        self.assertNotIn('answer', chat.call_args.kwargs['format_schema']['properties'])

    async def test_selected_native_tool_executes_and_result_reaches_model(self):
        session = LocalSession({'system_instruction': 'Test', 'declarations': DECLARATIONS,
                                'adaptive_tools': True}, speech=Mock(synthesize=Mock(return_value=b'')))
        answers = [{'tool_calls': [{'function': {'name': 'weather_report', 'arguments': {'city': 'Newport News'}}}]},
                   {'content': 'It is 62 degrees.'}]
        observed = []
        def chat(messages, tools, **kwargs):
            observed.append((messages, tools))
            return answers.pop(0)
        with patch('core.tool_catalog.select_tools', return_value={'weather_report'}), patch.object(home_llm, 'chat', side_effect=chat):
            task = asyncio.create_task(session._turn([{'text': 'Weather please'}]))
            while True:
                event = await asyncio.wait_for(session.events.get(), 2)
                if event.tool_call:
                    from types import SimpleNamespace
                    await session.send_tool_response([SimpleNamespace(id=event.tool_call.function_calls[0].id, name='weather_report', response={'result': '62 degrees'})])
                    session.tool_done.set()  # receive() acknowledges dispatch after the consumer resumes.
                    break
            await asyncio.wait_for(task, 2)
        self.assertEqual(observed[0][1][0]['function']['name'], 'weather_report')
        self.assertTrue(any(m['role'] == 'tool' and '62 degrees' in m['content'] for m in observed[1][0]))

    def test_unknown_route_is_rejected(self):
        with patch.object(home_llm, 'chat', return_value={'content': '{"tools":["invented"],"answer":""}'}):
            with self.assertRaises(ValueError):
                select_tools('test', [], DECLARATIONS)


class ToolTests(unittest.TestCase):
    def test_progress_does_not_create_another_model_turn(self):
        import main
        app = object.__new__(main.JarvisLive)
        app.ui = Mock()
        app.speak = Mock()
        app._tool_progress('Looking up the weather')
        app.ui.write_log.assert_called_once()
        app.speak.assert_not_called()

    def test_dev_agent_nonzero_exit_and_timeout_are_failures(self):
        from actions.dev_agent import _has_error
        self.assertTrue(_has_error('Exit code: 1', 'python app.py'))
        self.assertTrue(_has_error('Timed out after 30s', 'python app.py'))

    def test_dispatch_rejects_missing_arguments_before_handler(self):
        handler = Mock()
        record = ActionRecord(name='test', valid=True, handler=handler, parameters=DECLARATIONS[0]['parameters'])
        registry = ActionRegistry({'test': record}, lambda _: None)
        self.assertIn('failed', registry.run('test', {}))
        handler.assert_not_called()

    def test_empty_handler_result_is_not_success(self):
        record = ActionRecord(name='test', valid=True, handler=lambda parameters: None)
        result = ActionRegistry({'test': record}, lambda _: None).run('test', {})
        self.assertIn('unverified', result)

    def test_search_returns_sources_without_model_summary(self):
        from actions import web_search
        with patch.object(web_search, '_ddg_search', return_value=[{'title': 'Evidence', 'snippet': 'Fact', 'url': 'https://example.org'}]), patch.object(home_llm, 'chat') as chat:
            result = web_search.web_search({'query': 'test'})
        self.assertIn('https://example.org', result)
        chat.assert_not_called()

    def test_bad_flight_dates_never_default_to_today(self):
        from actions.flight_finder import _parse_date
        for value in ['2026-02-30', '03/04/2026', 'sometime', '2026-10-15 junk']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                _parse_date(value)
        self.assertEqual(_parse_date('October 15, 2026'), '2026-10-15')

    def test_flight_url_has_no_stale_encoded_itinerary(self):
        from actions.flight_finder import _build_google_flights_url
        self.assertNotIn('tfs=', _build_google_flights_url('JFK', 'LAX', '2026-10-15'))

    def test_generated_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ['../outside.py', 'C:/outside.py', '/outside.py', 'sub/../../x', 'file:stream']:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    child_path(folder, name)

    def test_archive_is_preflighted_before_any_file_written(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'test.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('safe.txt', 'test')
                z.writestr('../outside.txt', 'bad')
            with self.assertRaises(ValueError):
                extract_archive(archive, root / 'out')
            self.assertFalse((root / 'out/safe.txt').exists())

    def test_archive_extracts_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'test.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('sub/test.txt', 'original')
            extract_archive(archive, root / 'out')
            self.assertEqual((root / 'out/sub/test.txt').read_text(), 'original')
            with self.assertRaises(ValueError):
                extract_archive(archive, root / 'out')

    def test_failed_video_conversion_is_not_reported_as_saved(self):
        from actions.file_processor import _process_video
        with patch('actions.file_processor.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'ffmpeg')):
            result = _process_video(Path('example.mp4'), 'convert', {'format': 'webm'})
        self.assertNotIn('Saved:', result)

    def test_volume_failure_does_not_claim_success(self):
        from actions import computer_settings as settings
        with patch.object(settings, 'volume_get', return_value=30), patch.object(settings, 'volume_set', side_effect=RuntimeError('device missing')):
            result = settings.computer_settings({'action': 'volume_set', 'value': 50})
        self.assertIn('Could not set volume', result)

    def test_unknown_desktop_action_does_not_generate_code(self):
        from actions import desktop
        with patch.object(desktop, '_ask_gemini_for_desktop_action') as model:
            result = desktop.desktop_control({'action': 'typo'})
        self.assertIn('Unknown', result)
        model.assert_not_called()
