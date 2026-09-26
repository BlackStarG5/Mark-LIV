import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS
from actions.project_workspace import project_workspace
from actions.malware_scan import malware_scan
from actions.gpu_diagnostics import gpu_diagnostics
from core.tool_catalog import quick_route


class PartnerToolsTests(unittest.TestCase):
    def test_project_creation_verifies_saved_content_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = str(Path(folder)/'mod')
            self.assertTrue(json.loads(project_workspace({'action': 'init', 'root': root}))['verified'])
            args = {'action': 'create', 'root': root, 'path': 'src/Main.java', 'content': 'class Main {}'}
            self.assertTrue(json.loads(project_workspace(args))['ok'])
            self.assertEqual((Path(root)/'src/Main.java').read_text(), 'class Main {}')
            with self.assertRaises(FileExistsError):
                project_workspace(args)
            with self.assertRaises(ValueError):
                project_workspace({**args, 'path': '../escape.java'})

    def test_scan_requires_explicit_path(self):
        with self.assertRaises(ValueError):
            malware_scan({'action': 'start'})
        with self.assertRaises(ValueError):
            malware_scan({'action': 'start', 'path': 'Downloads'})

    def test_scan_retains_target_no_remediation_and_pending_is_not_clean(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder)/'MpCmdRun.exe'
            exe.touch()
            with patch('actions.malware_scan.defender_executable', return_value=exe), patch('actions.malware_scan.command_runner', return_value=json.dumps({'ok': False, 'status': 'running', 'job_id': 'test-scan'})) as command:
                data = json.loads(malware_scan({'action': 'start', 'path': folder}))
            self.assertIn('-DisableRemediation', command.call_args.args[0]['argv'])
            self.assertEqual(data['scan_path'], str(Path(folder).resolve()))
            self.assertIn('still running', data['answer'])
            with patch('actions.malware_scan.command_runner', return_value=json.dumps({'ok': False, 'status': 'finished', 'job_id': 'test-scan', 'exit_code': 2})):
                data = json.loads(malware_scan({'action': 'poll', 'job_id': 'test-scan'}))
            self.assertIn('detections or a scan failure', data['answer'])

    def test_gpu_query_failure_does_not_claim_health(self):
        with patch('actions.gpu_diagnostics.shutil.which', return_value='nvidia-smi.exe'), patch('actions.gpu_diagnostics.subprocess.run', return_value=NS(returncode=1, stderr='driver failed')):
            self.assertFalse(json.loads(gpu_diagnostics({}))['ok'])

    def test_gpu_csv_retains_units_and_driver(self):
        with patch('actions.gpu_diagnostics.shutil.which', return_value='nvidia-smi.exe'), patch('actions.gpu_diagnostics.subprocess.run', return_value=NS(returncode=0, stdout='RTX 3060, 999, 50, 1000, 12000, 60, 100, 170, P0\n')):
            data = json.loads(gpu_diagnostics({}))
        self.assertEqual(data['gpus'][0]['driver_version'], '999')
        self.assertEqual(data['units']['memory'], 'MiB')

    def test_coding_routes_to_build_workflow(self):
        names = {'project_workspace', 'command_runner', 'web_search', 'developer_environment', 'game_updater'}
        self.assertEqual(quick_route('Build a Minecraft mod with IntelliJ', [], names), names - {'game_updater'})

    def test_security_and_gpu_routes(self):
        self.assertEqual(quick_route('Run a malware scan on this directory', [], {'malware_scan', 'file_controller'}), {'malware_scan'})
        self.assertEqual(quick_route('My GPU is having issues', [], {'gpu_diagnostics', 'system_status'}), {'gpu_diagnostics'})
