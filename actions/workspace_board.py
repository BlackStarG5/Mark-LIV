"""Persistent notes and project cards shared by JARVIS and its dashboard."""
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from core.agent_support import result, stamp

PATH = Path(__file__).resolve().parent.parent / 'memory' / 'workspace_board.db'


def workspace_board(parameters):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(PATH, timeout=3)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS cards (id TEXT PRIMARY KEY, kind TEXT, title TEXT, body TEXT, updated TEXT)')
        action = parameters['action']
        if action == 'list':
            rows = db.execute('SELECT * FROM cards ORDER BY updated DESC LIMIT 100').fetchall()
            return result(ok=True, cards=[dict(zip(('id','kind','title','body','updated'), row)) for row in rows])
        if action in ('add', 'update'):
            kind, title, body = parameters.get('kind','note'), parameters.get('title','').strip(), parameters.get('body','')
            if kind not in ('note','project') or not title or len(title)>200 or len(body)>10000:
                raise ValueError('Use note/project, a title of 1–200 characters and body up to 10000 characters.')
            key = parameters.get('id') if action == 'update' else uuid.uuid4().hex[:12]
            if action == 'update':
                count = db.execute('UPDATE cards SET kind=?, title=?, body=?, updated=? WHERE id=?', (kind,title,body,stamp(),key)).rowcount
                return result(ok=bool(count), id=key)
            db.execute('INSERT INTO cards VALUES (?,?,?,?,?)',(key,kind,title,body,stamp()))
            return result(ok=True,id=key)
        raise ValueError('Choose list, add or update.')


TOOL = {'name':'workspace_board','description':'Read or maintain persistent dashboard notes and project cards. List before updating by ID. Save requested notes or project summaries; never mark unverified work successful.',
        'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['list','add','update']},'id':{'type':'STRING'},'kind':{'type':'STRING','enum':['note','project']},'title':{'type':'STRING'},'body':{'type':'STRING'}},'required':['action'],'additionalProperties':False},'handler':workspace_board}
