import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import chat_store as store


class ChatStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.override=patch.object(store,'ROOT',Path(self.temp.name)/'Jarvis');self.override.start();store.set_active('regular')

    def tearDown(self):
        store.set_active('regular');self.override.stop();self.temp.cleanup()

    def test_chat_history_and_automatic_title_persist(self):
        chat=store.create_chat();history=[{'role':'user','content':'Plan my Minecraft mod'},{'role':'assistant','content':'Which version?'}]
        store.save_history(history,chat)
        self.assertEqual(store.get_chat(chat)['title'],'Plan my Minecraft mod')
        self.assertEqual(store.load_history(chat),history)

    def test_private_project_blocks_outside_history_and_media(self):
        store.save_history([{'role':'user','content':'outside banana secret'}])
        source=Path(self.temp.name)/'shared.txt';source.write_text('shared')
        shared=store.import_media(source)
        project=store.create_project('Work',False);chat=store.create_chat(project);store.set_active(chat)
        self.assertEqual(store.search('banana'),[]);self.assertEqual(store.list_media(),[])
        store.save_history([{'role':'user','content':'private apple secret'}])
        private=store.import_media(source)
        self.assertNotEqual(shared['path'],private['path'])
        self.assertTrue(Path(private['path']).is_relative_to(Path(store.get_chat()['folder'])))
        store.set_active('regular')
        self.assertEqual(store.search('apple'),[])
        self.assertEqual([r['id'] for r in store.list_media()],[shared['id']])

    def test_project_chats_share_context_and_shared_project_can_retrieve_regular(self):
        store.save_history([{'role':'user','content':'shared reference'}])
        project=store.create_project('Shared',True);chat=store.create_chat(project);store.set_active(chat)
        self.assertTrue(store.search('reference'))
        private=store.create_project('Private');one=store.create_chat(private);two=store.create_chat(private)
        store.save_history([{'role':'user','content':'project reference'}],one);store.set_active(two)
        self.assertEqual(store.search('reference')[0]['chat_id'],one)

    def test_reusing_media_does_not_duplicate_and_archive_survives_trim(self):
        source=Path(self.temp.name)/'file.txt';source.write_text('hello')
        media=store.import_media(source)
        self.assertEqual(store.import_media(media['path'])['id'],media['id'])
        history=[{'role':'user','content':'One'},{'role':'assistant','content':'Two'},{'role':'user','content':'Three'}]
        store.save_history(history)
        store.save_history(history[2:]+[{'role':'assistant','content':'Four'}])
        self.assertEqual(len(store.load_history()),4)

    def test_repeated_messages_do_not_replace_archived_history(self):
        history=[{'role':'user','content':'Hi'},{'role':'assistant','content':'Hello'},{'role':'user','content':'Hi'}]
        store.save_history(history)
        store.save_history(history[-1:]+[{'role':'assistant','content':'Again'}])
        self.assertEqual(store.load_history(),history+[{'role':'assistant','content':'Again'}])

    def test_notes_and_tasks_are_scoped_in_private_projects(self):
        import json
        from actions.workspace_board import workspace_board
        from actions.task_list import task_list
        with patch('actions.workspace_board.PATH',Path(self.temp.name)/'notes.db'),patch('actions.task_list.PATH',Path(self.temp.name)/'tasks.db'):
            workspace_board({'action':'add','kind':'note','title':'Regular note','body':'Outside'})
            task_list({'action':'add','title':'Regular task'})
            project=store.create_project('Private');store.set_active(store.create_chat(project))
            self.assertEqual(json.loads(workspace_board({'action':'list'}))['cards'],[])
            self.assertEqual(json.loads(task_list({'action':'list'}))['tasks'],[])
            workspace_board({'action':'add','kind':'note','title':'Work note','body':'Inside'})
            store.set_active('regular')
            self.assertEqual([c['title'] for c in json.loads(workspace_board({'action':'list'}))['cards']],['Regular note'])
