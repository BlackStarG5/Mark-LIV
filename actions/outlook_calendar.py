"""Outlook calendar through delegated Graph access, plus offline event drafts."""
from datetime import datetime, timezone
from pathlib import Path
import uuid
import requests
from core.agent_support import result
from core.outlook_auth import token

DRAFTS = Path.home() / 'Documents' / 'JARVIS Calendar Drafts'
GRAPH = 'https://graph.microsoft.com/v1.0'


def interval(parameters):
    start, end = (datetime.fromisoformat(parameters[k]) for k in ('start', 'end'))
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError('Start and end require explicit ISO timezone offsets.')
    if not 0 < (end-start).total_seconds() <= 366*86400:
        raise ValueError('End must follow start, and the range must be at most 366 days.')
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def escape(value):
    return str(value).replace('\\', '\\\\').replace('\r', '').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold(line):
    chunks, current = [], ''
    for char in line:
        if len((current+char).encode('utf-8')) > 73:
            chunks.append(current)
            current = ' '
        current += char
    return '\r\n'.join(chunks+[current])


def outlook_calendar(parameters):
    action = parameters['action']
    if action == 'draft':
        start, end = interval(parameters)
        title = parameters.get('title', '').strip()
        if not title or len(title) > 500:
            raise ValueError('Provide an event title of 1–500 characters.')
        DRAFTS.mkdir(parents=True, exist_ok=True)
        identity = uuid.uuid4().hex
        path = DRAFTS / (identity+'.ics')
        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//JARVIS//Calendar Draft//EN', 'BEGIN:VEVENT',
                 f'UID:{identity}@jarvis.local', 'DTSTAMP:'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                 'DTSTART:'+start.strftime('%Y%m%dT%H%M%SZ'), 'DTEND:'+end.strftime('%Y%m%dT%H%M%SZ'),
                 'SUMMARY:'+escape(title), 'DESCRIPTION:'+escape(parameters.get('description', '')[:4000]), 'END:VEVENT', 'END:VCALENDAR']
        path.write_bytes(('\r\n'.join(fold(line) for line in lines)+'\r\n').encode('utf-8'))
        return result(ok=True, draft_file=str(path), calendar_saved=False,
                      note='Event file prepared. Open it in Outlook and save/import it. No event has been added to your calendar yet.')
    access = token()
    if not access:
        return result(ok=False, connected=False, setup='Run connect_outlook.py after registering a Microsoft public-client application. No password/API key should be pasted into chat. Offline draft action works without connection.')
    headers = {'Authorization': 'Bearer '+access, 'Prefer': 'outlook.timezone="UTC"'}
    if action == 'status':
        response = requests.get(GRAPH+'/me/calendar', headers=headers, timeout=(3, 10))
        response.raise_for_status()
        return result(ok=True, connected=True, calendar_name=response.json().get('name'), source='Microsoft Graph; default Outlook calendar')
    start, end = interval(parameters)
    if action in ('events', 'conflicts'):
        response = requests.get(GRAPH+'/me/calendarView', headers=headers, params={'startDateTime': start.isoformat(), 'endDateTime': end.isoformat(), '$top': 50, '$select': 'id,subject,start,end,showAs,isCancelled,webLink', '$orderby': 'start/dateTime'}, timeout=(3, 10))
        response.raise_for_status(); body = response.json()
        events = body.get('value', [])
        if action == 'conflicts':
            events = [e for e in events if not e.get('isCancelled') and e.get('showAs') != 'free']
        return result(ok=True, events=events, partial=bool(body.get('@odata.nextLink')), timezone='UTC')
    if action == 'create':
        title = parameters.get('title', '').strip()
        if not title or len(title) > 500:
            raise ValueError('Provide an event title of 1–500 characters.')
        payload = {'subject': title, 'start': {'dateTime': start.replace(tzinfo=None).isoformat(), 'timeZone': 'UTC'},
                   'end': {'dateTime': end.replace(tzinfo=None).isoformat(), 'timeZone': 'UTC'},
                   'body': {'contentType': 'text', 'content': parameters.get('description', '')[:4000]},
                   'transactionId': str(uuid.uuid5(uuid.NAMESPACE_URL, title+start.isoformat()+end.isoformat()))}
        try:
            response = requests.post(GRAPH+'/me/events', headers=headers, json=payload, timeout=(3, 10))
        except requests.RequestException:
            return result(ok=False, outcome='unknown', note='Creation response unavailable. Check the calendar before retrying; the event may already exist.')
        if response.status_code >= 500:
            return result(ok=False, outcome='unknown', note='Microsoft returned a server error. Check the calendar before retrying this creation.')
        response.raise_for_status()
        event = response.json()
        event_id = event.get('id')
        if not event_id:
            return result(ok=False, outcome='unknown', note='Creation returned no event ID; check calendar before retrying.')
        from urllib.parse import quote
        try:
            check = requests.get(GRAPH+'/me/events/'+quote(event_id, safe=''), headers=headers, timeout=(3, 10))
            check.raise_for_status()
            saved = check.json()
            def utc(field):
                value = datetime.fromisoformat(saved[field]['dateTime'])
                return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
            verified = (saved.get('id') == event_id and saved.get('subject') == title
                        and utc('start') == start and utc('end') == end)
        except (requests.RequestException, ValueError, KeyError):
            verified = False
        return result(ok=True, created=True, readback_verified=verified, event_id=event_id, web_link=event.get('webLink'),
                      note='Personal event only; no attendees/invitations. Creation succeeded; readback status is separate.')
    raise ValueError('Choose status, events, conflicts, create or draft.')


TOOL = {'name': 'outlook_calendar', 'description': 'Windows Outlook calendar: connection status, events or conflicts in an explicit date range, create a requested personal event, or prepare offline ICS draft. Requires Microsoft connection except draft. ISO start/end must include timezone offsets. Draft is not a saved calendar event.',
        'parameters': {'type': 'OBJECT', 'properties': {'action': {'type': 'STRING', 'enum': ['status', 'events', 'conflicts', 'create', 'draft']}, 'start': {'type': 'STRING'}, 'end': {'type': 'STRING'}, 'title': {'type': 'STRING'}, 'description': {'type': 'STRING'}}, 'required': ['action']}, 'handler': outlook_calendar}
