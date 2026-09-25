"""Download local speech models and render short samples without playing them."""
from pathlib import Path
import wave
from core.local_session import LocalSpeech
from memory import config_manager


def main():
    speech = LocalSpeech()
    from faster_whisper import WhisperModel
    from core.home_llm import load_config
    WhisperModel(load_config().get("stt_model", "small"), device="cpu", compute_type="int8")
    folder = Path(__file__).resolve().parent / "voice-samples"
    folder.mkdir(exist_ok=True)
    from unittest.mock import patch
    for voice in config_manager.AVAILABLE_VOICES:
        with patch.object(config_manager, "get_voice", return_value=voice):
            pcm = speech.synthesize("Hello. Your home AI is ready. What would you like to work on?")
            speech.startup_audio()
        with wave.open(str(folder / f"{voice}.wav"), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24000)
            output.writeframes(pcm)
        print(f"Saved {voice}.wav")


if __name__ == "__main__":
    main()
