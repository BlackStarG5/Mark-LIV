import json
import unittest
from unittest.mock import Mock, patch
from core.cpu_diagnostics import diagnose_cpu
from core.direct_requests import direct_request
from core.tool_catalog import quick_route
from types import SimpleNamespace


class CpuDiagnosticsTests(unittest.TestCase):
    def test_report_discards_baselines_and_idle_and_normalizes_process_cpu(self):
        proc = Mock(pid=12)
        proc.name.return_value = 'game.exe'
        proc.create_time.return_value = 123
        proc.cpu_times.side_effect = [SimpleNamespace(user=x, system=0) for x in (0, .8, 2.4)]
        with patch('core.cpu_diagnostics.psutil.process_iter', side_effect=lambda: [Mock(pid=0), proc]), patch('core.cpu_diagnostics.psutil.cpu_count', return_value=8), patch('core.cpu_diagnostics.psutil.cpu_percent', side_effect=[99, 20, 40]), patch('core.cpu_diagnostics.time.sleep'), patch('core.cpu_diagnostics.time.monotonic', side_effect=[0, 0, 1, 2, 2, 2]):
            data = json.loads(diagnose_cpu(samples=2))
        self.assertEqual(data['system_average_cpu_percent'], 30)
        self.assertEqual(data['top_processes'][0]['average_cpu_percent'], 15)
        self.assertEqual(data['top_processes'][0]['peak_cpu_percent'], 20)
        self.assertEqual(len(data['top_processes']), 1)

    def test_exact_failed_user_request_executes_without_model(self):
        text = 'Jarvis, my CPU is spiking randomly. Can you find the causes or possible causes of why my CPU is spiking?'
        self.assertEqual(direct_request(text), ('environment_inspect', {'scope': 'cpu_diagnostics'}))
        self.assertEqual(quick_route(text, [], {'environment_inspect', 'system_status'}), {'environment_inspect'})

    def test_never_swallow_server_or_mutation_requests(self):
        self.assertIsNone(direct_request('Investigate CPU spikes on my server'))
        self.assertIsNone(direct_request('Find the CPU spike cause and kill that process'))


class DiagnosticIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnostic_request_runs_tool_and_answers_without_model(self):
        from core.local_session import LocalSession
        from actions.environment_inspect import TOOL
        with patch('core.cpu_diagnostics.diagnose_cpu', return_value=json.dumps({'ok': True, 'answer': 'Observed game.exe at 20% CPU.'})) as diagnostic, patch('core.task_journal.record'), patch('core.home_llm.chat') as model:
            session = LocalSession({'system_instruction': 'Test', 'declarations': [TOOL], 'direct_requests': True}, speech=SimpleNamespace(synthesize=lambda _: b''))
            await session._turn([{'text': 'My CPU is spiking randomly. Can you find the causes?'}])
        diagnostic.assert_called_once()
        model.assert_not_called()
        self.assertIn('game.exe', session.history[-1]['content'])
