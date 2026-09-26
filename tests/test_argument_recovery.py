import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from core.local_session import LocalSession


class ArgumentRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_batch_does_not_execute_and_corrected_call_does(self):
        declaration={'name':'project_workspace','parameters':{'type':'OBJECT','properties':{'root':{'type':'STRING'},'action':{'type':'STRING'}},'required':['root','action']}}
        session=LocalSession({'system_instruction':'Test','declarations':[declaration],'adaptive_tools':True},speech=NS(synthesize=lambda _:b''))
        with tempfile.TemporaryDirectory() as folder:
            bad={'tool_calls':[{'function':{'name':'project_workspace','arguments':{'action':'read'}}}]}
            good={'tool_calls':[{'function':{'name':'project_workspace','arguments':{'action':'read','root':folder}}}]}
            with patch('core.tool_catalog.select_tools',return_value={'project_workspace'}),patch.object(session,'_model_reply',new=AsyncMock(side_effect=[bad,good,{'content':'Read verified.'}])) as reply,patch('core.task_journal.record'):
                task=asyncio.create_task(session._turn([{'text':'Read the project'}]))
                event=await asyncio.wait_for(session.events.get(),3)
                self.assertEqual(event.tool_call.function_calls[0].args['root'],folder)
                session.tool_results=[NS(name='project_workspace',response={'result':'{"ok":true}'})]
                session.tool_done.set()
                await asyncio.wait_for(task,3)
                self.assertEqual(reply.call_count,3)
                self.assertIn('No tools in this batch ran',reply.call_args_list[1].args[0][-1]['content'])
                self.assertEqual(session.history[-1]['content'],'Read verified.')

    async def test_bad_arguments_stop_after_bounded_corrections(self):
        declaration={'name':'project_workspace','parameters':{'type':'OBJECT','properties':{'root':{'type':'STRING'}},'required':['root']}}
        session=LocalSession({'system_instruction':'Test','declarations':[declaration],'adaptive_tools':True},speech=NS(synthesize=lambda _:b''))
        bad={'tool_calls':[{'function':{'name':'project_workspace','arguments':{}}}]}
        with patch('core.tool_catalog.select_tools',return_value={'project_workspace'}),patch.object(session,'_model_reply',new=AsyncMock(return_value=bad)) as reply:
            with self.assertRaisesRegex(ValueError,'two correction attempts'):
                await session._turn([{'text':'Read my project'}])
            self.assertEqual(reply.call_count,3)
            self.assertTrue(session.events.empty())
