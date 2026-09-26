"""Read-only measurements of this process, this PC, and the Ollama endpoint."""
import os
import platform
import time
import re
import psutil
import requests
from core import home_llm, runtime_state
from core.agent_support import result


def inspect_process(target=None, pid=None):
    """Match executable names or installation folders; never substitute PC totals."""
    def normalized(value):
        return re.sub(r'[^a-z0-9]', '', value.casefold())
    needle = normalized(target or '')
    if pid is None and len(needle) < 3:
        raise ValueError('Supply a process name of at least three characters or a PID.')
    rows = []
    inaccessible = 0
    for process in psutil.process_iter():
        try:
            if pid is not None and process.pid != pid:
                continue
            name = process.name()
            if pid is None and needle not in normalized(name):
                # Installation folders allow friendly names such as Marvel Rivals.
                if needle not in normalized(process.exe()):
                    continue
            rss = process.memory_info().rss
            rows.append({'pid': process.pid, 'name': name, 'rss_bytes': rss})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            inaccessible += 1
    if not rows:
        return result(ok=False, scope='process', target=target, pid=pid,
                      answer='No accessible matching process was found. I cannot report its memory usage.',
                      inaccessible_processes=inaccessible)
    rows.sort(key=lambda row: row['rss_bytes'], reverse=True)
    total = sum(row['rss_bytes'] for row in rows)
    names = ', '.join(sorted({row['name'] for row in rows}))
    return result(ok=True, scope='process', target=target, processes=rows,
                  rss_bytes=total, memory_metric='resident working set (RSS)',
                  memory_note='Includes shared pages; summed processes may count shared pages more than once. Task Manager may display private working set instead.',
                  answer=f'Matching processes ({names}; {len(rows)} total) use {total / 2**30:.2f} GiB of resident RAM, including shared memory.')


def inspect_environment(parameters):
    unknown = set(parameters) - {'scope', 'target', 'pid'}
    if unknown:
        raise ValueError('Unsupported environment parameters: ' + ', '.join(sorted(unknown)))
    scope = parameters.get('scope', 'app')
    if scope == 'cpu_diagnostics':
        if parameters.get('target') is not None or parameters.get('pid') is not None:
            raise ValueError('CPU diagnostics samples all accessible processes; omit target and pid.')
        from core.cpu_diagnostics import diagnose_cpu
        return diagnose_cpu()
    target, pid = parameters.get('target'), parameters.get('pid')
    if target is not None and (not isinstance(target, str) or not target.strip()):
        raise ValueError('target must be a nonempty process name.')
    if pid is not None and (type(pid) is not int or pid <= 0):
        raise ValueError('pid must be a positive integer.')
    if target is not None and pid is not None:
        raise ValueError('Use either target or pid, not both.')
    if target is not None or pid is not None:
        if scope not in ('app', 'process'):
            raise ValueError('Process targets require app or process scope.')
        scope = 'process'
    if scope == 'process':
        return inspect_process(target, pid)
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
            data['answer'] = f"The whole PC uses {pc['ram_used_gb']} of {pc['ram_total_gb']} GiB RAM ({pc['ram_percent']}%). CPU busy time averaged over one second is {pc['cpu_percent']}%."
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


TOOL = {'name': 'environment_inspect', 'description': 'Investigate CPU spikes or heavy CPU consumers with cpu_diagnostics (two-interval process sampling). Measure JARVIS (app), a named application (process with target or pid), whole PC, speech device, or Ollama server. YOUR usage means app. Never substitute PC or JARVIS totals for another application. Report the measured subject and memory metric.',
        'parameters': {'type': 'OBJECT', 'properties': {'scope': {'type': 'STRING', 'enum': ['app', 'process', 'cpu_diagnostics', 'pc', 'speech', 'server', 'all']}, 'target': {'type': 'STRING', 'description': 'Application name, e.g. Marvel Rivals'}, 'pid': {'type': 'INTEGER', 'description': 'Exact process ID instead of target'}}, 'required': ['scope'], 'additionalProperties': False}, 'handler': inspect_environment}
