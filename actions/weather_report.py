"""Fetch readable weather data without opening a browser."""
from datetime import date, timedelta
from functools import lru_cache
import requests


def _get(url, params):
    response = requests.get(url, params=params, timeout=(5, 10))
    response.raise_for_status()
    data = response.json()
    if data.get('error'):
        raise ValueError(data.get('reason', 'Weather service error'))
    return data


@lru_cache(maxsize=64)
def _locate(city):
    pieces = [p.strip() for p in city.split(',') if p.strip()]
    results = _get('https://geocoding-api.open-meteo.com/v1/search',
                   {'name': pieces[0], 'count': 10, 'language': 'en', 'format': 'json'}).get('results', [])
    for qualifier in pieces[1:]:
        qualifier = {'usa': 'us', 'united states of america': 'us', 'uk': 'gb'}.get(qualifier.lower(), qualifier.lower())
        results = [r for r in results if qualifier in
                   {str(r.get(k, '')).lower() for k in ('admin1', 'admin2', 'country', 'country_code')}]
    if not results:
        raise ValueError('Location not found. Please provide the city and full state or country name.')
    exact = [r for r in results if r.get('name', '').casefold() == pieces[0].casefold()]
    if exact:
        results = exact
    if len(results) > 1:
        places = {', '.join(filter(None, (r.get('name'), r.get('admin1'), r.get('country')))) for r in results}
        if len(places) > 1:
            raise ValueError('Please clarify which location: ' + '; '.join(sorted(places)[:5]))
    return results[0]


def weather_action(parameters: dict, player=None, session_memory=None) -> str:
    city = parameters.get('city')
    if not isinstance(city, str) or not city.strip():
        return 'Please provide a city for the weather report.'
    try:
        place = _locate(city.strip())
        unit = parameters.get('unit') or ('fahrenheit' if place.get('country_code') == 'US' else 'celsius')
        if unit not in ('fahrenheit', 'celsius'):
            return 'Choose Fahrenheit or Celsius for the temperature unit.'
        when = str(parameters.get('time') or 'current').strip().lower()
        if when not in ('now', 'current', 'today', 'tomorrow'):
            try:
                date.fromisoformat(when)
            except ValueError:
                return 'Specify current weather, today, tomorrow, or a date as YYYY-MM-DD.'
        data = _get('https://api.open-meteo.com/v1/forecast', {
            'latitude': place['latitude'], 'longitude': place['longitude'],
            'current': 'temperature_2m,apparent_temperature',
            'daily': 'temperature_2m_max,temperature_2m_min',
            'temperature_unit': unit, 'timezone': 'auto', 'forecast_days': 7,
        })
        location = ', '.join(filter(None, (place['name'], place.get('admin1'), place.get('country'))))
        current = data['current']
        stamp = current['time']
        if when in ('now', 'current'):
            temperature = current['temperature_2m']
            if not isinstance(temperature, (int, float)):
                raise ValueError('The service did not return a current temperature.')
            result = f'It is currently {temperature:g} degrees {unit.title()} in {location}.'
            feels = current.get('apparent_temperature')
            if isinstance(feels, (int, float)):
                result += f' It feels like {feels:g} degrees.'
        else:
            today = date.fromisoformat(stamp[:10])
            target = (today if when == 'today' else today + timedelta(days=1) if when == 'tomorrow'
                      else date.fromisoformat(when)).isoformat()
            daily = data['daily']
            if target not in daily['time']:
                return 'That date is outside the available seven-day forecast.'
            index = daily['time'].index(target)
            high, low = daily['temperature_2m_max'][index], daily['temperature_2m_min'][index]
            if not all(isinstance(v, (int, float)) for v in (high, low)):
                raise ValueError('The service did not return a forecast for that date.')
            result = f'For {target} in {location}, the forecast high is {high:g} and low is {low:g} degrees {unit.title()}.'
        result += f' Source: Open-Meteo (https://open-meteo.com/), as of {stamp} {data.get("timezone", "local time")}.'
        if session_memory:
            try:
                session_memory.set_last_search(query=f'weather {city} {when}', response=result)
            except Exception:
                pass
        return result
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as exc:
        return f'Weather lookup unavailable: {exc}. No browser was opened.'


TOOL = {
    'name': 'weather_report',
    'description': 'Fetch current temperature or a daily forecast as readable data. No browser is opened. Use this to answer weather questions aloud, including requests not to open a webpage.',
    'parameters': {
        'type': 'OBJECT',
        'properties': {
            'city': {'type': 'STRING', 'description': 'City, full state name, country; for example Newport News, Virginia, United States'},
            'time': {'type': 'STRING', 'description': 'current (default), today, tomorrow, or YYYY-MM-DD within seven days'},
            'unit': {'type': 'STRING', 'enum': ['fahrenheit', 'celsius'], 'description': 'Defaults to Fahrenheit in the US, Celsius elsewhere'},
        },
        'required': ['city'],
    },
    'handler': weather_action,
}
