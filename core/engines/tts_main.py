import logging
import time
import numpy as np
import sounddevice as sd
import os
import torch # CRITICAL: Exposes CUDA DLLs for ONNX Runtime (Must be before onnxruntime import)
import onnxruntime as rt

# CRITICAL: Set Espeak Library Path for Phonemizer BEFORE importing Kokoro
# This fixes the "EspeakWrapper has no attribute set_data_path" error
# caused by phonemizer not finding the shared library automatically on Windows.
os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = r"C:\Program Files\eSpeak NG\libespeak-ng.dll"

# MONKEY PATCH: Fix for kokoro-onnx calling non-existent set_data_path
try:
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    if not hasattr(EspeakWrapper, 'set_data_path'):
        print("Applying Patch: EspeakWrapper.set_data_path = no-op")
        EspeakWrapper.set_data_path = lambda path: None
except ImportError:
    pass

from kokoro_onnx import Kokoro

logger = logging.getLogger(__name__)

class TTSMain:
    """
    Main TTS Engine using Kokoro (GPU/ONNX).
    Attributes: High Quality, Natural Prosody.
    """
    def __init__(self, model_path="kokoro-v0_19.onnx", voices_path="voices.json"):
        self.voices_path = "voices.bin"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.kokoro = None
        self.sample_rate = 24000
        
        # Check available providers from ONNX Runtime
        providers = rt.get_available_providers()
        logger.info(f"Available ONNX Providers: {providers}")
        
        # HYBRID SELECTION LOGIC
        # 1. GPU (CUDA) -> Use FP32 Model (Verified ~0.5s latency)
        if 'CUDAExecutionProvider' in providers:
            logger.info("GPU Detected! Using CUDA Acceleration.")
            os.environ["ONNX_PROVIDER"] = "CUDAExecutionProvider" # Force CUDA (avoid TensorRT issues)
            self.model_path = "kokoro-v0_19.onnx"
            
        # 2. CPU -> Use Int8 Model (Verified ~0.85s latency)
        elif os.path.exists("kokoro-v1.0.int8.onnx"):
            logger.info("CPU Detected. Using Quantized Model (Int8) for speed.")
            self.model_path = "kokoro-v1.0.int8.onnx"
            
        # 3. CPU Fallback
        else:
            logger.warning("CPU Detected and No Int8 model found. Using FP32 (Slow ~1.0s).")
            self.model_path = "kokoro-v0_19.onnx"
            
        # Start initialization
        self.load_model() 

    def load_model(self):
        logger.info("Loading Kokoro TTS...")
        try:
            abs_path = os.path.abspath(self.model_path)
            logger.info(f"Looking for Kokoro Model at: {abs_path}")
            
            # Verify files exist, else warn (User might need to download them manually)
            if not os.path.exists(self.model_path):
                logger.warning(f"Kokoro model not found at {self.model_path}. Please download kokoro-v0_19.onnx")
                return

            self.kokoro = Kokoro(self.model_path, self.voices_path)
            logger.info("Kokoro TTS Loaded.")
            
            # WARMUP: Run a silent inference to eat the initial ~5s delay
            logger.info("Warming up Kokoro (First inference is slow)...")
            self.kokoro.create("Warmup.", voice="af_bella", speed=1.0)
            logger.info("Kokoro Warmup Complete.")
            
        except Exception as e:
            logger.critical(f"Failed to load Kokoro: {e}")

    def synthesize(self, text, voice="af_bella", speed=1.0):
        """
        Synthesizes text to audio chunks.
        Returns: list of audio segments (numpy arrays).
        """
        if not self.kokoro:
            logger.error("Kokoro not loaded.")
            return None, None

        start_time = time.time()
        
        # Kokoro synthesis
        # Returns (samples, sample_rate)
        samples, sr = self.kokoro.create(
            text, 
            voice=voice, 
            speed=speed, 
            lang="en-us"
        )
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Kokoro synthesized {len(text)} chars in {elapsed:.1f}ms")
        
        return samples, sr
