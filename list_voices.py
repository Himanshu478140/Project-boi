
import os
import json

# MONKEY PATCH: Fix for kokoro-onnx calling non-existent set_data_path
try:
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    if not hasattr(EspeakWrapper, 'set_data_path'):
        EspeakWrapper.set_data_path = lambda path: None
except ImportError:
    pass

from kokoro_onnx import Kokoro

def list_voices():
    model_path = "kokoro-v0_19.onnx"
    voices_path = "voices.bin"
    
    if not os.path.exists(model_path) or not os.path.exists(voices_path):
        print("Model or voices file not found.")
        return

    print("Loading Kokoro...")
    kokoro = Kokoro(model_path, voices_path)
    
    print("\n--- Available Voices ---")
    # Kokoro-onnx 0.3+ exposes voices via .get_voice_names() or .voices attribute
    # We'll try inspection
    
    if hasattr(kokoro, "get_voice_names"):
        voices = kokoro.get_voice_names()
        for v in sorted(voices):
            print(f"- {v}")
    elif hasattr(kokoro, "voices"):
        voices = kokoro.voices.keys()
        for v in sorted(voices):
            print(f"- {v}")
    else:
        print("Could not find method to list voices. Inspecting object dir:")
        print(dir(kokoro))

if __name__ == "__main__":
    list_voices()
