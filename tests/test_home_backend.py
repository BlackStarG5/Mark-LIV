import asyncio
import copy
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from core import home_llm
from core.local_session import LocalSession

CONFIG = {"system_instruction": "Test assistant", "declarations": [
    {"name": "screen_process", "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}}, "required": ["text"]}},
    {"name": "read_file", "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}}, "required": ["path"]}},
]}


class Speech:
    def synthesize(self, text):
        return b"\0\0" * 240

    def transcribe(self, pcm):
        return "hello"


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_voice_logs_once_but_keeps_all_response_text(self):
        logs = []
        speech = Speech()
        session = LocalSession(CONFIG, speech=speech, log=logs.append)
        with patch.object(speech, "synthesize", side_effect=ModuleNotFoundError("No module named 'torch'")) as synth:
            await session._speak_text("First sentence. Second sentence.")
            await session._speak_text("Another reply.")
        self.assertEqual(synth.call_count, 1)
        self.assertEqual(len(logs), 1)
        self.assertIn("pip install -r", logs[0])
        texts = []
        while not session.events.empty():
            texts.append(session.events.get_nowait().server_content.output_transcription.text)
        self.assertEqual(texts, ["First sentence.", "Second sentence.", "Another reply."])

    async def collect(self, session, handler=None):
        output = []
        async for ev in session.receive():
            output.append(ev)
            if ev.tool_call:
                await handler(ev.tool_call.function_calls)
            if ev.server_content.turn_complete:
                return output

    async def test_multi_tool_rounds_and_vision_attach_before_next_inference(self):
        observed = []
        answers = [
            {"tool_calls": [{"function": {"name": "screen_process", "arguments": {"text": "read screen"}}}]},
            {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "example.txt"}}}]},
            {"content": "The answer is forty two."},
        ]
        def chat(messages, tools):
            observed.append(copy.deepcopy(messages))
            return answers.pop(0)
        history = []
        session = LocalSession(CONFIG, history, Speech())
        async def handler(calls):
            await session.send_tool_response([NS(name=calls[0].name, response={"result": "ok"})])
            if calls[0].name == "screen_process":
                await session.send_client_content({"parts": [{"inline_data": {"mime_type": "image/png", "data": "eA=="}}]})
        with patch.object(home_llm, "models", return_value=[{"name": "qwen3:8b"}]), patch.object(home_llm, "chat", side_effect=chat), patch.object(home_llm, "describe_images", return_value="Screen says example.txt"):
            async with session:
                await session.send_client_content({"parts": [{"text": "Read the file shown on screen"}]})
                events = await asyncio.wait_for(self.collect(session, handler), 3)
        self.assertEqual(len(observed), 3)
        self.assertIn("Screen says example.txt", observed[1][-1]["content"])
        self.assertEqual(observed[2][-1]["tool_name"], "read_file")
        self.assertTrue(any(e.data for e in events))
        self.assertEqual(history[-1]["content"], "The answer is forty two.")

    async def test_invalid_tool_arguments_do_not_reach_dispatch(self):
        logs = []
        session = LocalSession(CONFIG, speech=Speech(), log=logs.append)
        answer = {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": 42}}}]}
        with patch.object(home_llm, "models", return_value=[{"name": "qwen3:8b"}]), patch.object(home_llm, "chat", return_value=answer):
            async with session:
                await session.send_client_content({"parts": [{"text": "read"}]})
                events = await asyncio.wait_for(self.collect(session), 3)
        self.assertFalse(any(e.tool_call for e in events))
        self.assertIn("failed", logs[0])
        self.assertEqual(session.history, [])

    async def test_network_failure_retains_previous_history_and_allows_next_turn(self):
        history = [{"role": "user", "content": "old"}, {"role": "assistant", "content": "remembered"}]
        session = LocalSession(CONFIG, history, Speech(), log=lambda _: None)
        with patch.object(home_llm, "models", return_value=[{"name": "qwen3:8b"}]), patch.object(home_llm, "chat", side_effect=[RuntimeError("offline"), {"content": "Recovered."}]):
            async with session:
                await session.send_client_content({"parts": [{"text": "first"}]})
                await asyncio.wait_for(self.collect(session), 3)
                self.assertEqual(len(history), 2)
                await session.send_client_content({"parts": [{"text": "second"}]})
                await asyncio.wait_for(self.collect(session), 3)
        self.assertEqual(history[-1]["content"], "Recovered.")

    async def test_interrupt_discards_queued_tool_before_dispatch(self):
        session = LocalSession(CONFIG, speech=Speech(), log=lambda _: None)
        answer = {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "example.txt"}}}]}
        with patch.object(home_llm, "models", return_value=[{"name": "qwen3:8b"}]), patch.object(home_llm, "chat", return_value=answer):
            async with session:
                await session.send_client_content({"parts": [{"text": "read"}]})
                async def wait_pending():
                    while session.events.empty():
                        await asyncio.sleep(0.01)
                await asyncio.wait_for(wait_pending(), 3)
                session.interrupt()
                events = await asyncio.wait_for(self.collect(session), 3)
                self.assertFalse(any(e.tool_call for e in events))
                self.assertEqual(session.history, [])


class TransportTests(unittest.TestCase):
    @patch.object(home_llm, "load_config", return_value={"llm_url": "http://test:11434", "llm_model": "qwen3:8b"})
    @patch.object(home_llm.requests, "post")
    def test_thinking_and_model_routing(self, post, config):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"message": {"content": "ok"}}
        home_llm.chat([{"role": "user", "content": "hi"}])
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "qwen3:8b")
        self.assertIs(body["think"], False)
        home_llm.describe_images([{"inline_data": {"mime_type": "image/png", "data": b"image"}}])
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "qwen3.5:9b")
        self.assertEqual(body["messages"][-1]["images"], ["aW1hZ2U="])

    @patch.object(home_llm, "load_config", return_value={"llm_url": "http://test:11434", "llm_model": "qwen3:8b"})
    @patch.object(home_llm.requests, "post")
    def test_identity_uses_configured_model_without_mutating_history(self, post, config):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"message": {"content": "ok"}}
        messages = [{"role": "system", "content": "You are JARVIS."}, {"role": "user", "content": "Which model?"}]
        home_llm.chat(messages)
        prompt = post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertIn("qwen3:8b", prompt)
        self.assertIn("Ollama", prompt)
        self.assertIn("You are JARVIS.", prompt)
        self.assertEqual(messages[0]["content"], "You are JARVIS.")
        home_llm.chat(messages, model="qwen3.5:9b")
        self.assertIn("qwen3.5:9b", post.call_args.kwargs["json"]["messages"][0]["content"])

    def test_property_named_type_keeps_its_schema(self):
        schema = {"type": "OBJECT", "properties": {"type": {"type": "STRING"}}}
        self.assertEqual(home_llm.normalize_schema(schema),
                         {"type": "object", "properties": {"type": {"type": "string"}}})

    @patch.object(home_llm, "load_config", return_value={"llm_url": "http://user:secret@host"})
    def test_credentials_in_url_rejected(self, config):
        with self.assertRaises(ValueError):
            home_llm.settings()


if __name__ == "__main__":
    unittest.main()
