import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from actions.workspace_board import workspace_board


class BoardTests(unittest.TestCase):
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
