import unittest
from unittest.mock import patch
from core.tool_catalog import select_tools,requires_web

class RequiredSearchTests(unittest.TestCase):
    def test_explicit_followup_cannot_be_vetoed(self):
        declarations=[{'name':'web_search','parameters':{'type':'OBJECT','properties':{}}}]
        history=[{'role':'user','content':'When is the new Switch Ocarina of Time game coming out?'},{'role':'assistant','content':'There is no announced version.'}]
        with patch('core.tool_catalog.home_llm.chat') as router:
            route=select_tools('Look it up on the web and tell me again. There is a new version coming out. I need the release date for 2026. Thank you',history,declarations)
        self.assertEqual(route,{'web_search'});self.assertEqual(route.mode,'observe');router.assert_not_called()

    def test_current_release_questions_require_retrieval(self):
        for text in ['When is the new Switch Ocarina of Time game coming out','What is the release date for the next game?','Check that online','Search the internet for this','What is the current price?']:
            with self.subTest(text=text): self.assertTrue(requires_web(text))

    def test_no_browse_and_non_web_tasks_do_not_force_search(self):
        for text in ["Don't search the web; explain what a release date means",'Look at my screen','Search my documents','What is my name?']:
            with self.subTest(text=text): self.assertFalse(requires_web(text))
