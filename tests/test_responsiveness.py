import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch, AsyncMock

from actions import weather_report as weather
from core.local_session import LocalSpeech, event

PLACE = {'name': 'Newport News', 'admin1': 'Virginia', 'country': 'United States', 'country_code': 'US', 'latitude': 37, 'longitude': -76}
DATA = {'current': {'time': '2026-09-24T19:00', 'temperature_2m': 72, 'apparent_temperature': 70},
        'timezone': 'America/New_York', 'daily': {'time': ['2026-09-24', '2026-09-25'],
        'temperature_2m_max': [78, 80], 'temperature_2m_min': [60, 62]}}

class WeatherTests(unittest.TestCase):
    def setUp(self):
        weather._locate.cache_clear()

    def test_current_temperature_without_browser(self):
        with patch.object(weather, '_get', side_effect=[{'results': [dict(PLACE, name='Newport News Park'), PLACE]}, DATA]), patch('webbrowser.open') as browser:
            result = weather.weather_action({'city': 'Newport News, Virginia'})
        self.assertIn('72 degrees Fahrenheit', result)
        self.assertIn('2026-09-24T19:00', result)
        browser.assert_not_called()

    def test_ambiguous_location_does_not_guess(self):
        with patch.object(weather, '_get', return_value={'results': [PLACE, dict(PLACE, admin1='Ohio')]}):
            result = weather.weather_action({'city': 'Newport News'})
        self.assertIn('clarify', result)

    def test_tomorrow_uses_forecast_not_current_temperature(self):
        with patch.object(weather, '_locate', return_value=PLACE), patch.object(weather, '_get', return_value=DATA):
            result = weather.weather_action({'city': 'Newport News', 'time': 'tomorrow'})
        self.assertIn('2026-09-25', result)
        self.assertIn('high is 80 and low is 62', result)

    def test_network_error_does_not_open_browser(self):
        with patch.object(weather, '_get', side_effect=weather.requests.Timeout('timeout')), patch('webbrowser.open') as browser:
            result = weather.weather_action({'city': 'Newport News'})
        self.assertIn('unavailable', result)
        browser.assert_not_called()

class VoiceCacheTests(unittest.TestCase):
    def test_short_reply_cache_respects_voice_and_stays_in_memory(self):
        from memory import config_manager
        speech = LocalSpeech()
        with patch.object(speech, '_synthesize', return_value=b'\0\0') as synth:
            with patch.object(config_manager, 'get_voice', return_value='bm_george'):
                speech.synthesize('Hello.')
                speech.synthesize('Hello.')
            with patch.object(config_manager, 'get_voice', return_value='bm_fable'):
                speech.synthesize('Hello.')
        self.assertEqual(synth.call_count, 2)

class UITests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_transcripts_log_separately_before_response_finishes(self):
        import main
        logs = []
        async def receive():
            yield event(heard='First question?')
            yield event(heard='Second question?')
            raise asyncio.CancelledError()
        app = object.__new__(main.JarvisLive)
        app.ui = NS(write_log=logs.append)
        app.session = NS(receive=receive)
        app._session_log = []
        app._dashboard = None
        with self.assertRaises(asyncio.CancelledError):
            await app._receive_audio()
        self.assertEqual(logs, ['You: First question?', 'You: Second question?'])

    async def test_default_news_displays_without_model_turn(self):
        import main
        app = object.__new__(main.JarvisLive)
        displayed = asyncio.Event()
        app.ui = NS(write_log=lambda _: None, show_content=lambda *args: displayed.set())
        app._turn_done_event = asyncio.Event()
        async def greeting():
            app._turn_done_event.set()
        app.session = NS(say_startup=greeting, send_client_content=AsyncMock())
        with patch.object(main, 'load_memory', return_value={}), patch.object(main, 'pop_last_session', return_value=None), patch.object(main, '_fetch_news_sync', return_value='Example headline'), patch('core.home_llm.load_config', return_value={}):
            await app._send_startup_briefing()
            await asyncio.wait_for(displayed.wait(), 3)
            await asyncio.sleep(0)
        app.session.send_client_content.assert_not_called()

if __name__ == '__main__':
    unittest.main()
