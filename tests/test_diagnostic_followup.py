import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch, AsyncMock
from core.direct_requests import direct_request
from core.tool_catalog import quick_route
from core.tool_catalog import select_tools
from actions.environment_inspect import TOOL

FOLLOWUP = "Ah, so what you're saying is that mobile rivals is probably causing my stuttering plus my CPU spikages?"


class FollowupTests(unittest.TestCase):
    def test_contextual_decision_receives_tool_evidence_and_can_clarify(self):
        history = [{'role': 'tool', 'tool_name': 'environment_inspect', 'content': 'Marvel CPU averaged 46.4%'}]
        with patch('core.home_llm.chat', return_value={'content': '{"mode":"clarify","tools":[]}'}) as model:
            self.assertEqual(select_tools('Investigate the CPU on that machine', history, [TOOL]), set())
        self.assertIn('46.4%', model.call_args.args[0][-1]['content'])

    def test_interpretation_does_not_scan_or_route_to_status(self):
        self.assertIsNone(direct_request(FOLLOWUP))
        self.assertEqual(quick_route(FOLLOWUP, [], {'environment_inspect', 'system_status'}), set())

    def test_explicit_new_reading_still_runs(self):
        text = 'So what you are saying is CPU spikes? Check my CPU spikes again.'
        self.assertEqual(direct_request(text), ('environment_inspect', {'scope': 'cpu_diagnostics'}))

    def test_initial_question_still_runs(self):
        text = "Jarvis, what's consuming most of my CPU at the moment? I see it spiking to around 90%, and I would just want to figure out what the cause issue is."
        self.assertEqual(direct_request(text), ('environment_inspect', {'scope': 'cpu_diagnostics'}))


class FollowupIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_clarification_decision_reaches_reply_model(self):
        from core.local_session import LocalSession
        from core.tool_catalog import ToolSelection
        session = LocalSession({'system_instruction': 'Test', 'declarations': [TOOL], 'adaptive_tools': True}, speech=NS(synthesize=lambda _: b''))
        with patch('core.tool_catalog.select_tools', return_value=ToolSelection(mode='clarify')), patch.object(session, '_model_reply', new_callable=AsyncMock, return_value={'content': 'Which directory should I scan?'}) as reply:
            await session._turn([{'text': 'Scan that folder.'}])
        self.assertEqual(session.turn_tools, [])
        self.assertTrue(any('This turn requires clarification' in m.get('content', '') for m in reply.call_args.args[0]))

    async def test_followup_uses_previous_evidence_without_any_tool_call(self):
        from core.local_session import LocalSession
        from actions.environment_inspect import TOOL
        history = [{'role': 'user', 'content': 'Investigate CPU spikes'}, {'role': 'assistant', 'content': 'Marvel-Win64-Shipping.exe averaged 46.4% CPU; total CPU was 87.1%.'}]
        session = LocalSession({'system_instruction': 'Interpret prior readings.', 'declarations': [TOOL], 'direct_requests': True, 'adaptive_tools': True}, history=history, speech=NS(synthesize=lambda _: b''))
        with patch('actions.environment_inspect.inspect_environment') as scan, patch.object(session, '_model_reply', new_callable=AsyncMock, return_value={'content': 'Marvel Rivals was the largest observed CPU consumer; that may contribute to stutter.'}) as reply:
            await session._turn([{'text': FOLLOWUP}])
        scan.assert_not_called()
        self.assertEqual(session.turn_tools, [])
        self.assertTrue(any('46.4%' in m.get('content', '') for m in reply.call_args.args[0]))
        self.assertIn('largest observed', session.history[-1]['content'])
