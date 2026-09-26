import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from actions.workspace_board import workspace_board
from actions.workspace_board import TOOL
from actions.task_list import TOOL as TASK
from core.tool_catalog import select_tools


class BoardTests(unittest.TestCase):
    def test_note_and_note_correction_never_route_to_conversation_or_task(self):
        history=[{'role':'user','content':'Add a new task to take out trash.'}, {'role':'assistant','content':'Task saved.'}]
        for prompt in ('Jarvis, can you make a note to set my apples out on the counter at 12 a.m. please?', "Hey Jarvis, you still haven't made that note for me about the apples. Could you go ahead and do that? I don't see it in the notes."):
            with patch('core.home_llm.chat') as model:
                self.assertEqual(select_tools(prompt,history,[TOOL,TASK]),{'workspace_board'})
                model.assert_not_called()

    def test_retry_of_identical_note_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as folder, patch('actions.workspace_board.PATH', Path(folder)/'board.db'):
            args={'action':'add','title':'Apples','body':'Set apples out at 12 a.m.'}
            first=json.loads(workspace_board(args));second=json.loads(workspace_board(args))
            self.assertEqual(first['id'],second['id'])
            self.assertTrue(second['already_exists'])
            self.assertEqual(len(json.loads(workspace_board({'action':'list'}))['cards']),1)

    def test_board_persists_and_updates_same_card(self):
        with tempfile.TemporaryDirectory() as folder, patch('actions.workspace_board.PATH', Path(folder)/'board.db'):
            created=json.loads(workspace_board({'action':'add','kind':'project','title':'Mod','body':'Next: choose loader'}))
            cards=json.loads(workspace_board({'action':'list'}))['cards']
            self.assertEqual(cards[0]['body'],'Next: choose loader')
            workspace_board({'action':'update','id':created['id'],'kind':'project','title':'Mod','body':'Next: build'})
            cards=json.loads(workspace_board({'action':'list'}))['cards']
            self.assertEqual(len(cards),1)
            self.assertEqual(cards[0]['body'],'Next: build')
            self.assertFalse(json.loads(workspace_board({'action':'update','id':'missing','title':'Missing'}))['ok'])
