"""Read NVIDIA driver telemetry; never tune clocks or terminate workloads."""
import csv
import io
import os
from pathlib import Path
import shutil
import subprocess
from core.agent_support import result


def gpu_diagnostics(parameters):
    executable = shutil.which('nvidia-smi')
    if not executable:
        candidate = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/nvidia-smi.exe'
        executable = str(candidate) if candidate.exists() else None
    if not executable:
        return result(ok=False, answer='NVIDIA driver telemetry is unavailable: nvidia-smi was not found.')
    fields = ['name', 'driver_version', 'utilization.gpu', 'memory.used', 'memory.total', 'temperature.gpu', 'power.draw', 'power.limit', 'pstate']
    try:
        response = subprocess.run([executable, '--query-gpu=' + ','.join(fields), '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if response.returncode:
            return result(ok=False, error=response.stderr[-2000:], answer='The NVIDIA driver query failed; GPU health is not established.')
        rows = [dict(zip(fields, [value.strip() for value in row])) for row in csv.reader(io.StringIO(response.stdout)) if row]
        answer = ' '.join(f"{r['name']}: {r['utilization.gpu']}% GPU usage, {r['memory.used']} of {r['memory.total']} MiB VRAM, {r['temperature.gpu']} degrees Celsius, driver {r['driver_version']}." for r in rows)
        return result(ok=bool(rows), gpus=rows, units={'memory': 'MiB', 'power': 'watts', 'temperature': 'Celsius'},
                      answer=answer or 'The driver returned no GPU measurements.', limitations='Point-in-time driver readings do not establish the cause of stutter, hardware failure, or historical driver resets. N/A means unavailable.')
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result(ok=False, answer='GPU telemetry could not be obtained.', error=str(exc))


TOOL = {'name': 'gpu_diagnostics', 'description': 'Investigate local NVIDIA GPU issues: driver version, GPU load, VRAM, temperature, power and performance state. Measurements only; cannot alone prove hardware health or explain past stutter.',
        'parameters': {'type': 'OBJECT', 'properties': {}, 'additionalProperties': False}, 'handler': gpu_diagnostics}
