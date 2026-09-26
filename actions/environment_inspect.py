"""Read-only measurements of this process, this PC, and the Ollama endpoint."""
import os
import platform
import time
import psutil
import requests
from core import home_llm, runtime_state
from core.agent_support import result


def inspect_environment(parameters):
    scope = parameters.get('scope', 'app')
    data = {'scope': scope, 'client_hostname': platform.node()}
    if scope in ('app', 'all'):
        process = psutil.Process(os.getpid())
        rss = process.memory_info().rss
        children = []
        for child in process.children(recursive=True):
            try:
                children.append({'pid': child.pid, 'name': child.name(), 'rss_bytes': child.memory_info().rss})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        app = {'pid': process.pid, 'rss_bytes': rss, 'rss_gib': round(rss / 2**30, 3),
               'cpu_percent_one_core_100': process.cpu_percent(interval=.1),
               'uptime_seconds': round(time.time() - process.create_time()), 'children': children,
               'memory_note': 'RSS is resident memory, including shared pages; child RSS is separate and may overlap.'}
        data['app'] = app
        data['answer'] = f'This JARVIS process uses {rss / 2**30:.2f} GiB of resident RAM. That is application memory, not total PC usage.'
    if scope in ('pc', 'all'):
        from actions.system_monitor import get_system_status
        data['pc'] = get_system_status()
        data['pc']['memory_units'] = 'GiB (legacy keys use gb)'
        if scope == 'pc':
            pc = data['pc']
            data['answer'] = f"The whole PC uses {pc['ram_used_gb']} of {pc['ram_total_gb']} GiB RAM ({pc['ram_percent']}%). CPU usage is {pc['cpu_percent']}%."
    if scope in ('speech', 'all'):
        data['speech'] = runtime_state.snapshot()
        import sys
        torch = sys.modules.get('torch')
        if torch is not None and torch.cuda.is_initialized():
            data['speech'].update(cuda_allocated_bytes=torch.cuda.memory_allocated(), cuda_reserved_bytes=torch.cuda.memory_reserved(),
                                  gpu= torch.cuda.get_device_name(0), memory_note='PyTorch allocator only; excludes driver overhead and other processes.')
    if scope in ('server', 'all'):
        url, model = home_llm.settings()
        server = {'endpoint': url, 'configured_model': model, 'host_cpu_ram': 'Unavailable: Ollama does not expose whole-server CPU/RAM here.'}
        try:
            start = time.perf_counter()
            response = requests.get(url + '/api/ps', headers=home_llm._headers(), timeout=(2, 4))
            response.raise_for_status()
            server.update(reachable=True, request_seconds=round(time.perf_counter()-start, 3),
                          loaded_models=[{k: row.get(k) for k in ('name', 'size', 'size_vram', 'expires_at')} for row in response.json().get('models', [])])
        except (requests.RequestException, ValueError) as exc:
            server.update(reachable=False, error=type(exc).__name__)
        data['server'] = server
    if scope not in ('app', 'pc', 'speech', 'server', 'all'):
        raise ValueError('Choose app, pc, speech, server or all.')
    return result(ok=True, **data)


TOOL = {'name': 'environment_inspect', 'description': 'Measure JARVIS application RAM/CPU, whole PC, observed speech device, or home Ollama server. Ask about YOUR usage means scope=app. Never substitute PC totals for process memory.',
        'parameters': {'type': 'OBJECT', 'properties': {'scope': {'type': 'STRING', 'enum': ['app', 'pc', 'speech', 'server', 'all']}}, 'required': ['scope']}, 'handler': inspect_environment}
