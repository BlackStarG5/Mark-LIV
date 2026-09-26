"""Observed speech backend state, shared with read-only diagnostics."""
import threading

_lock = threading.Lock()
_state = {'tts_device': 'not initialized', 'stt_device': 'cpu'}


def update(**values):
    with _lock:
        _state.update(values)


def snapshot():
    with _lock:
        return dict(_state)
