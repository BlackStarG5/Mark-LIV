import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import numpy as np
from core import home_llm
from core.local_session import LocalSpeech, LocalSession

class RecognitionTests(unittest.TestCase):
    def test_vocabulary_is_hint_not_transcript_replacement(self):
        speech=LocalSpeech()
        speech.stt=NS(transcribe=Mock(return_value=([NS(text='What is Sinnerware?')], None)))
        with patch.object(home_llm,'load_config',return_value={'stt_vocabulary':['Incineroar','Pokémon'],'stt_beam_size':3}):
            result=speech.transcribe(b'\0\0'*1600)
        self.assertEqual(result,'What is Sinnerware?')
        options=speech.stt.transcribe.call_args.kwargs
        self.assertEqual(options['beam_size'],3)
        self.assertIn('Incineroar',options['hotwords'])
        self.assertFalse(options['condition_on_previous_text'])
        self.assertIsNone(options['language'])

class AudioCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def test_quiet_opening_audio_is_retained(self):
        captured=[]
        def transcribe(pcm):
            captured.append(pcm)
            return 'Hello'
        session=LocalSession({'system_instruction':'Test','declarations':[]},speech=NS(transcribe=transcribe))
        quiet=np.full(1600,100,dtype='<i2').tobytes()
        loud=np.full(3200,1000,dtype='<i2').tobytes()
        silence=np.zeros(3200,dtype='<i2').tobytes()
        for chunk in (quiet,loud,silence):
            await session.audio.put(chunk)
        with patch.object(home_llm,'load_config',return_value={'speech_silence_seconds':0.2}):
            worker=asyncio.create_task(session._audio_worker())
            try:
                heard=await asyncio.wait_for(session.events.get(),2)
                self.assertEqual(heard.server_content.input_transcription.text,'Hello')
            finally:
                worker.cancel()
                await asyncio.gather(worker,return_exceptions=True)
        self.assertEqual(captured[0],quiet+loud+silence)

if __name__=='__main__': unittest.main()
