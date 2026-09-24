"""Check the launcher's interpreter before opening the voice UI."""
import importlib.util
from pathlib import Path
import sys

MODULES = ("PyQt6", "numpy", "requests", "sounddevice", "faster_whisper", "torch", "kokoro", "jsonschema")


def main():
    missing = [name for name in MODULES if importlib.util.find_spec(name) is None]
    if not missing:
        return 0
    requirements = Path(__file__).resolve().parent / "requirements.txt"
    print("Home AI cannot start: this Python environment is incomplete.")
    print("Python:", sys.executable)
    print("Missing:", ", ".join(missing))
    print("Run this command, then launch Start-HomeAI.cmd again:")
    print(f'"{sys.executable}" -m pip install -r "{requirements}"')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
