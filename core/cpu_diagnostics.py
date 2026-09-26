"""Bounded, read-only CPU sampling. No process termination or configuration changes."""
import time
import psutil
from core.agent_support import result


def diagnose_cpu(samples=2, interval=1.0):
    cores = psutil.cpu_count() or 1
    tracked = {}
    previous = {}
    totals = []
    rows = {}
    unavailable = set()
    started = time.monotonic()
    # Discover once, then reuse process handles rather than enumerate every tick.
    for proc in psutil.process_iter():
        if proc.pid == 0:
            continue
        try:
            key = (proc.pid, proc.create_time())
            name = proc.name()
            cpu = proc.cpu_times()
            previous[key] = (time.monotonic(), cpu.user + cpu.system)
            tracked[key] = proc
            rows[key] = {'pid': proc.pid, 'name': name, 'samples': []}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            unavailable.add(proc.pid)
    psutil.cpu_percent(interval=None)
    for index in range(samples):
        time.sleep(interval)
        totals.append(psutil.cpu_percent(interval=None))
        for key, proc in list(tracked.items()):
            try:
                cpu = proc.cpu_times()
                now = time.monotonic()
                before, used = previous[key]
                value = max(0.0, (cpu.user + cpu.system - used) / max(now-before, 0.001) / cores * 100)
                previous[key] = (now, cpu.user + cpu.system)
                rows[key]['samples'].append(round(value, 2))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                unavailable.add(proc.pid)
                del tracked[key]
    measured = []
    for row in rows.values():
        values = row.pop('samples')
        if values:
            measured.append({**row, 'average_cpu_percent': round(sum(values)/len(values), 2),
                             'peak_cpu_percent': max(values), 'sample_count': len(values)})
    measured.sort(key=lambda row: row['peak_cpu_percent'], reverse=True)
    average, peak = sum(totals)/len(totals), max(totals)
    leaders = measured[:5]
    details = '; '.join(f"{p['name']} (PID {p['pid']}): {p['average_cpu_percent']:.1f}% average, {p['peak_cpu_percent']:.1f}% peak" for p in leaders[:3])
    answer = (f'Over {time.monotonic()-started:.1f} seconds, total CPU averaged {average:.1f}% and peaked at {peak:.1f}%. '
              + ('The busiest observed processes were ' + details + '. ' if leaders else 'No process measurements were accessible. ')
              + 'These are observed CPU consumers, not proof of the cause of an earlier spike or mouse stutter.')
    return result(ok=True, scope='cpu_diagnostics', duration_seconds=round(time.monotonic()-started, 2),
                  system_average_cpu_percent=round(average, 1), system_peak_cpu_percent=peak,
                  system_samples=totals, top_processes=leaders, inaccessible_or_exited_processes=len(unavailable),
                  cpu_metric='Busy time; process percentages normalized to total logical CPU capacity',
                  limitations='Only this sampling window. Processes starting after discovery, brief/exited or inaccessible processes may be missed. No historical diagnosis, malware verdict, or driver attribution.',
                  answer=answer)
