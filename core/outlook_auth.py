"""Delegated Microsoft calendar authentication; Windows-protected token cache."""
from pathlib import Path
import threading
from core.home_llm import load_config

CACHE = Path(__file__).resolve().parent.parent / 'config' / 'outlook-cache.bin'
SCOPES = ['Calendars.ReadWrite']
_lock = threading.Lock()


def application(client_id):
    import msal
    import win32crypt
    cache = msal.SerializableTokenCache()
    if CACHE.exists():
        cache.deserialize(win32crypt.CryptUnprotectData(CACHE.read_bytes(), None, None, None, 0)[1].decode('utf-8'))
    app = msal.PublicClientApplication(client_id, authority='https://login.microsoftonline.com/common', token_cache=cache)
    return app, cache


def persist(cache):
    import win32crypt
    if cache.has_state_changed:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        temporary = CACHE.with_suffix('.tmp')
        temporary.write_bytes(win32crypt.CryptProtectData(cache.serialize().encode('utf-8'), 'JARVIS calendar', None, None, None, 0))
        temporary.replace(CACHE)


def token():
    client_id = load_config().get('outlook_client_id')
    if not client_id:
        return None
    with _lock:
        app, cache = application(client_id)
        accounts = app.get_accounts()
        response = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
        persist(cache)
    return response.get('access_token') if response else None


def connect(client_id):
    with _lock:
        app, cache = application(client_id)
        response = app.acquire_token_interactive(scopes=SCOPES, timeout=180)
        if 'access_token' not in response:
            raise RuntimeError('Microsoft sign-in did not complete: ' + response.get('error', 'cancelled'))
        persist(cache)
