"""Local chat archive, project context boundaries and copied media library."""
import json
import re
import shutil
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from core.agent_support import stamp

ROOT = Path.home() / 'Documents' / 'Jarvis'
_active = 'regular'
_lock = threading.RLock()


@contextmanager
def database():
    ROOT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ROOT/'library.db', timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            conn.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, title TEXT, folder TEXT, shared INTEGER)')
            conn.execute('CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT, project_id TEXT, history TEXT, updated TEXT)')
            conn.execute('CREATE TABLE IF NOT EXISTS media (id TEXT PRIMARY KEY, name TEXT, path TEXT, project_id TEXT, added TEXT)')
            conn.execute("INSERT OR IGNORE INTO chats VALUES ('regular','Regular chat',NULL,'[]',?)",(stamp(),))
            yield conn
    finally:
        conn.close()


def active_id():
    with _lock: return _active


def set_active(chat_id):
    global _active
    get_chat(chat_id)
    with _lock: _active=chat_id


def get_chat(chat_id=None):
    with database() as db:
        row=db.execute('SELECT chats.*, projects.title AS project_title, projects.folder, projects.shared FROM chats LEFT JOIN projects ON chats.project_id=projects.id WHERE chats.id=?',(chat_id or active_id(),)).fetchone()
        if row is None: raise ValueError('Chat not found.')
        return dict(row)


def private(chat_id=None):
    chat=get_chat(chat_id)
    return bool(chat['project_id'] and not chat['shared'])


def list_chats():
    with database() as db: return [dict(r) for r in db.execute('SELECT id,title,project_id,updated FROM chats ORDER BY updated DESC')]


def list_projects():
    with database() as db: return [dict(r) for r in db.execute('SELECT * FROM projects ORDER BY title')]


def create_project(title, shared=False):
    title=title.strip()
    if not title: raise ValueError('Project name required.')
    key=uuid.uuid4().hex[:12]
    slug=re.sub(r'[^\w -]', '', title)[:60].strip(' .') or 'Project'
    folder=ROOT/'Projects'/f'{slug}-{key}'
    folder.mkdir(parents=True)
    with database() as db: db.execute('INSERT INTO projects VALUES (?,?,?,?)',(key,title,str(folder),int(shared)))
    return key


def create_chat(project_id=None):
    key=uuid.uuid4().hex[:12]
    with database() as db:
        if project_id and not db.execute('SELECT id FROM projects WHERE id=?',(project_id,)).fetchone(): raise ValueError('Project not found.')
        db.execute('INSERT INTO chats VALUES (?,?,?,?,?)',(key,'New chat',project_id,'[]',stamp()))
    return key


def load_history(chat_id=None): return json.loads(get_chat(chat_id)['history'])


def save_history(history, chat_id=None):
    chat=get_chat(chat_id)
    previous=json.loads(chat['history'])
    if history and previous and history[:len(previous)] != previous:
        overlap=next((n for n in range(min(len(previous),len(history)),0,-1) if previous[-n:]==history[:n]),0)
        history=previous+history[overlap:]
    title=chat['title']
    if title=='New chat':
        first=next((m.get('content','') for m in history if m.get('role')=='user' and not m.get('content','').startswith('[')), '')
        if first: title=' '.join(first.split())[:64]
    with database() as db:
        db.execute('UPDATE chats SET title=?,history=?,updated=? WHERE id=?',(title,json.dumps(history,ensure_ascii=False),stamp(),chat['id']))


def allowed_project_ids(chat_id=None):
    chat=get_chat(chat_id)
    if private(chat['id']): return {chat['project_id']}
    with database() as db: return {None,*[r[0] for r in db.execute('SELECT id FROM projects WHERE shared=1')]}


def list_media(chat_id=None):
    allowed=allowed_project_ids(chat_id)
    with database() as db: return [dict(r) for r in db.execute('SELECT * FROM media ORDER BY added DESC') if r['project_id'] in allowed]


def import_media(source,chat_id=None):
    source=Path(source).resolve(strict=True)
    if not source.is_file(): raise ValueError('Choose a file.')
    for media in list_media(chat_id):
        if Path(media['path']).resolve()==source: return media
    chat=get_chat(chat_id);key=uuid.uuid4().hex
    directory=Path(chat['folder'])/'Media' if private(chat['id']) else ROOT/'Media'
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/(key+source.suffix)
    shutil.copy2(source,target)
    project_id=chat['project_id'] if private(chat['id']) else None
    with database() as db: db.execute('INSERT INTO media VALUES (?,?,?,?,?)',(key,source.name,str(target),project_id,stamp()))
    return {'id':key,'name':source.name,'path':str(target)}


def context():
    chat=get_chat();media=list_media()
    return (f"[Active local chat] {chat['title']}\nProject folder: {chat['folder'] or 'No project'}\n"
            f"Context policy: {'Project-only: do not read other projects, chats, global memory, or shared media.' if private() else 'Shared: authorized shared chats and media may be retrieved when relevant.'}\n"
            'Use chat_library to retrieve relevant saved conversations or list media; do not assume their contents.\n'
            + 'Available media: '+json.dumps([{'name':m['name'],'path':m['path']} for m in media[:20]]))


def search(query,limit=8):
    allowed=allowed_project_ids()
    found=[]
    with database() as db:
        for row in db.execute('SELECT * FROM chats ORDER BY updated DESC'):
            if row['project_id'] not in allowed: continue
            for msg in reversed(json.loads(row['history'])):
                text=msg.get('content','')
                if msg.get('role') in ('user','assistant') and not text.startswith('[Execution check]') and query.casefold() in text.casefold():
                    found.append({'chat_id':row['id'],'title':row['title'],'role':msg['role'],'text':text[:1500]})
                    if len(found)>=limit: return found
    return found


def scoped_path(default):
    if active_id()=='regular': return default
    chat=get_chat()
    return Path(chat['folder'])/'State'/Path(default).name if private() else default
