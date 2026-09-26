import asyncio
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from core import home_llm
from core.local_session import LocalSession, LocalSpeech, event
from core.tool_catalog import quick_route


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_collision_cancels_later_calls_in_same_batch(self):
        import main
        app = object.__new__(main.JarvisLive)
        app._execute_tool = AsyncMock(return_value=NS(response={'result': 'File already exists: test.txt'}))
        calls = [NS(id='create', name='file_controller'), NS(id='write', name='file_controller')]
        results = await app._execute_tool_batch(calls)
        self.assertEqual(app._execute_tool.call_count, 1)
        self.assertIn('Not executed', results[1].response['result'])

    async def test_vision_only_reply_skips_second_answer_model_call(self):
        declaration = {'name': 'screen_process', 'parameters': {'type': 'OBJECT', 'properties': {}}}
        session = LocalSession({'system_instruction': 'Test', 'declarations': [declaration], 'adaptive_tools': True, 'direct_vision': True},
                               speech=NS(synthesize=lambda _: b''))
        call = {'tool_calls': [{'function': {'name': 'screen_process', 'arguments': {}}}]}
        with patch('core.tool_catalog.select_tools', return_value={'screen_process'}), patch.object(home_llm, 'chat', return_value=call) as chat, patch.object(home_llm, 'describe_images', return_value='Chicken Pot Pie'):
            task = asyncio.create_task(session._turn([{'text': 'Read the sentence on my screen'}]))
            ev = await asyncio.wait_for(session.events.get(), 2)
            self.assertTrue(ev.tool_call)
            session.tool_results = [NS(name='screen_process', response={'result': 'Captured'})]
            session.images = [{'inline_data': {'mime_type': 'image/png', 'data': 'example'}}]
            session.tool_done.set()
            await asyncio.wait_for(task, 2)
        self.assertEqual(chat.call_count, 1)
        self.assertEqual(session.history[-1]['content'], 'Chicken Pot Pie')

    async def test_existing_file_stops_before_model_can_overwrite(self):
        declaration = {'name': 'file_controller', 'parameters': {'type': 'OBJECT', 'properties': {}}}
        session = LocalSession({'system_instruction': 'Test', 'declarations': [declaration], 'adaptive_tools': True},
                               speech=NS(synthesize=lambda _: b''))
        call = {'tool_calls': [{'function': {'name': 'file_controller', 'arguments': {}}}]}
        with patch('core.tool_catalog.select_tools', return_value={'file_controller'}), patch.object(home_llm, 'chat', return_value=call) as chat:
            task = asyncio.create_task(session._turn([{'text': 'Create test.txt unless it exists'}]))
            await asyncio.wait_for(session.events.get(), 2)
            session.tool_results = [NS(name='file_controller', response={'result': 'File already exists: test.txt. Nothing was changed.'})]
            session.tool_done.set()
            await asyncio.wait_for(task, 2)
        self.assertEqual(chat.call_count, 1)
        self.assertIn('already exists', session.history[-1]['content'])

    async def test_all_text_is_available_while_first_speech_is_blocked(self):
        release = threading.Event()
        speech = NS(synthesize=lambda text: (release.wait(3), b'')[1])
        session = LocalSession({'system_instruction': 'Test', 'declarations': []}, speech=speech)
        def chat(messages, tools, on_text, **kwargs):
            on_text('First sentence. Second sentence.')
            return {'content': 'First sentence. Second sentence.'}
        with patch.object(home_llm, 'chat', side_effect=chat):
            task = asyncio.create_task(session._turn([{'text': 'Tell me two sentences'}]))
            try:
                first = await asyncio.wait_for(session.events.get(), 1)
                second = await asyncio.wait_for(session.events.get(), 1)
                self.assertEqual(first.server_content.output_transcription.text, 'First sentence.')
                self.assertEqual(second.server_content.output_transcription.text, 'Second sentence.')
                self.assertFalse(task.done())
            finally:
                release.set()
                await task

    async def test_ui_displays_text_before_turn_complete(self):
        import main
        logs = []
        async def receive():
            yield event(text='Already visible.')
            self.assertEqual(logs, ['JARVIS: Already visible.'])
            raise asyncio.CancelledError()
        app = object.__new__(main.JarvisLive)
        app.ui = NS(write_log=logs.append)
        app.session = NS(receive=receive)
        app._asst_name = 'JARVIS'
        app._visemes = Mock()
        with self.assertRaises(asyncio.CancelledError):
            await app._receive_audio()

    async def test_identity_refresh_reaches_next_request(self):
        refresh = Mock(return_value={'system_instruction': 'Current name is Sam', 'session_context': 'Current time'})
        session = LocalSession({'system_instruction': 'Old name is Alex', 'declarations': [], 'refresh_context': refresh},
                               speech=NS(synthesize=lambda _: b''))
        with patch.object(home_llm, 'chat', return_value={'content': 'Sam'}) as chat:
            await session._turn([{'text': 'What is my name?'}])
        self.assertIn('Current name is Sam', chat.call_args.args[0][0]['content'])
        self.assertNotIn('Old name is Alex', chat.call_args.args[0][0]['content'])

    async def test_unexecuted_success_claim_is_never_published(self):
        declaration = {'name': 'file_controller', 'parameters': {'type': 'OBJECT', 'properties': {}}}
        session = LocalSession({'system_instruction': 'Test', 'declarations': [declaration], 'adaptive_tools': True},
                               speech=NS(synthesize=Mock(return_value=b'')))
        with patch('core.tool_catalog.select_tools', return_value={'file_controller'}), patch.object(home_llm, 'chat', return_value={'content': 'I edited the file.'}) as chat:
            with self.assertRaisesRegex(RuntimeError, 'No tool action'):
                await session._turn([{'text': 'Correct the file'}])
        self.assertEqual(chat.call_count, 2)
        self.assertTrue(session.events.empty())
        session.speech.synthesize.assert_not_called()


class ReliabilityTests(unittest.TestCase):
    def test_file_creation_does_not_overwrite(self):
        from actions import file_controller as files
        with tempfile.TemporaryDirectory() as folder, patch.object(files, '_is_safe_path', return_value=True), patch.object(files, 'push_undo'):
            target = Path(folder) / 'test.txt'
            target.write_text('Keep this')
            result = files.create_file(folder, 'test.txt', 'Overwrite')
            self.assertIn('already exists', result)
            self.assertEqual(target.read_text(), 'Keep this')

    def test_write_reads_back_and_verifies_content(self):
        from actions import file_controller as files
        with tempfile.TemporaryDirectory() as folder, patch.object(files, '_is_safe_path', return_value=True), patch.object(files, 'push_undo'):
            result = files.write_file(folder, 'test.txt', 'Apples\nGrapes\nOranges')
            self.assertIn('verified', result)
            self.assertEqual((Path(folder) / 'test.txt').read_text(), 'Apples\nGrapes\nOranges')

    def test_capture_defaults_to_both_monitors_and_can_select_second(self):
        from actions import screen_processor as screen
        capture = Mock()
        capture.monitors = [{'width': 3840}, {'width': 1920, 'left': 0}, {'width': 1920, 'left': 1920}]
        capture.grab.return_value = NS(rgb=b'pixels', size=(1, 1))
        factory = Mock()
        factory.return_value.__enter__ = Mock(return_value=capture)
        factory.return_value.__exit__ = Mock(return_value=False)
        with patch.object(screen.mss, 'mss', factory), patch.object(screen.mss.tools, 'to_png', return_value=b'png'), patch.object(screen, '_compress', return_value=(b'jpg', 'image/jpeg')):
            screen._capture_screen()
            capture.grab.assert_called_with(capture.monitors[0])
            screen._capture_screen(2)
            capture.grab.assert_called_with(capture.monitors[2])
            with self.assertRaises(ValueError):
                screen._capture_screen(3)

    def test_vocabulary_echo_is_rechecked_without_hints(self):
        speech = LocalSpeech()
        speech.stt = NS(transcribe=Mock(side_effect=[([NS(text='JARVIS, Pokémon, Incineroar, Newport News')], None), ([], None)]))
        config = {'stt_vocabulary': ['JARVIS', 'Pokémon', 'Incineroar', 'Newport News', 'Virginia']}
        with patch.object(home_llm, 'load_config', return_value=config):
            self.assertEqual(speech.transcribe(b'\0\0' * 1600), '')
        self.assertNotIn('hotwords', speech.stt.transcribe.call_args.kwargs)

    def test_low_confidence_silence_is_not_a_user_command(self):
        speech = LocalSpeech()
        speech.stt = NS(transcribe=Mock(return_value=([NS(text='Delete my files', no_speech_prob=.95, avg_logprob=-2)], None)))
        with patch.object(home_llm, 'load_config', return_value={}):
            self.assertEqual(speech.transcribe(b'\0\0' * 1600), '')

    def test_local_routes_are_contextual_and_conservative(self):
        names = {'file_controller', 'weather_report', 'system_status', 'screen_process', 'web_search'}
        self.assertEqual(quick_route('Read jarvis_test.txt', [], names), {'file_controller'})
        self.assertEqual(quick_route('Check RAM usage', [], names), {'system_status'})
        self.assertIsNone(quick_route('Explain what RAM does', [], names))
        self.assertIsNone(quick_route('Analyze my uploaded PDF', [], names))
        self.assertEqual(quick_route('Change that to hi instead', [{'role': 'tool', 'tool_name': 'file_controller'}], names), {'file_controller'})

    def test_publication_date_is_not_invented(self):
        from core.web_evidence import parse_page
        title, date, body = parse_page('<title>News</title><nav>menu</nav><article>Actual announcement</article>')
        self.assertEqual((title, date, body), ('News', '', 'Actual announcement'))
        self.assertEqual(parse_page('<meta property="article:published_time" content="2026-09-24"><article>News</article>')[1], '2026-09-24')

    def test_research_rejects_local_addresses(self):
        from core.web_evidence import public_url
        with patch('core.web_evidence.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]):
            with self.assertRaises(ValueError):
                public_url('http://localhost/private')
