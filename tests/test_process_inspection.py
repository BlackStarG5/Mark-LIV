import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import psutil
from actions.environment_inspect import inspect_environment
from core.direct_requests import direct_request
from core.tool_catalog import quick_route


class ProcessInspectionTests(unittest.TestCase):
    def test_friendly_name_matches_install_folder_and_never_own_process(self):
        game = Mock(pid=123)
        game.name.return_value = 'Marvel-Win64-Shipping.exe'
        game.exe.return_value = r'F:\Steam\MarvelRivals\Marvel\Marvel-Win64-Shipping.exe'
        game.memory_info.return_value = NS(rss=2**30)
        with patch('actions.environment_inspect.psutil.process_iter', return_value=[game]), patch('actions.environment_inspect.psutil.Process') as own:
            data = json.loads(inspect_environment({'scope': 'app', 'target': 'Marvel Rivals'}))
        own.assert_not_called()
        self.assertEqual(data['scope'], 'process')
        self.assertEqual(data['rss_bytes'], 2**30)
        self.assertEqual(data['processes'][0]['pid'], 123)
        self.assertNotIn('app', data)

    def test_missing_or_inaccessible_process_never_substitutes_measurement(self):
        denied = Mock()
        denied.name.side_effect = psutil.AccessDenied(123)
        with patch('actions.environment_inspect.psutil.process_iter', return_value=[denied]):
            data = json.loads(inspect_environment({'scope': 'process', 'target': 'missing'}))
        self.assertFalse(data['ok'])
        self.assertNotIn('rss_bytes', data)

    def test_invalid_parameters_are_not_silently_ignored(self):
        for parameters in ({'scope': 'pc', 'target': 'game'}, {'scope': 'app', 'application': 'game'}, {'scope': 'process'}, {'scope': 'process', 'pid': True}, {'scope': 'process', 'target': 'game', 'pid': 12}):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                inspect_environment(parameters)

    def test_exact_pid_does_not_include_other_processes(self):
        game = Mock(pid=123)
        game.name.return_value = 'game.exe'
        game.memory_info.return_value = NS(rss=1024)
        with patch('actions.environment_inspect.psutil.process_iter', return_value=[Mock(pid=99), game]):
            data = json.loads(inspect_environment({'scope': 'process', 'pid': 123}))
        self.assertEqual([p['pid'] for p in data['processes']], [123])

    def test_simple_memory_query_bypasses_model_without_catching_multistep(self):
        self.assertEqual(direct_request('How much RAM is Marvel Rivals currently using on my desktop?'), ('environment_inspect', {'scope': 'process', 'target': 'marvel rivals'}))
        self.assertIsNone(direct_request('How much memory is my server using?'))
        self.assertIsNone(direct_request('How much RAM is Marvel Rivals using and close it?'))

    def test_named_memory_routing_does_not_select_pc_only_tool(self):
        self.assertEqual(quick_route('Please tell me how much RAM Marvel Rivals is using', [], {'system_status', 'environment_inspect'}), {'environment_inspect'})

    def test_cpu_result_identifies_metric_and_sampling_window(self):
        from actions.system_monitor import get_system_status
        with patch('actions.system_monitor.psutil.cpu_percent', return_value=9) as cpu, patch('actions.system_monitor._get_cpu_temp', return_value=0), patch('actions.system_monitor._get_gpu_usage', return_value=0):
            data = get_system_status()
        cpu.assert_called_once_with(interval=1.0)
        self.assertEqual(data['cpu_sample_seconds'], 1.0)
        self.assertIn('busy time', data['cpu_metric'])
