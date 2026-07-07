import logging
import time
from faster_whisper import WhisperModel
import torch

logger = logging.getLogger(__name__)

class STTEngine:
    """
    Faster-Whisper Wrapper.
    Optimized for GPU (CUDA).
    """
    def __init__(self, model_size="Systran/faster-distil-whisper-large-v3", device="cuda", compute_type="float16"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        
        self.load_model()

    def load_model(self):
        logger.info(f"Loading Faster-Whisper ({self.model_size}) on {self.device}...")
        try:
            self.model = WhisperModel(
                self.model_size, 
                device=self.device, 
                compute_type=self.compute_type
            )
            logger.info("Faster-Whisper Loaded.")
        except Exception as e:
            logger.critical(f"Failed to load Faster-Whisper: {e}")
            raise

    def transcribe(self, audio_data, beam_size=1):
        if not self.model:
            return ""

        import numpy as np

        if isinstance(audio_data, np.ndarray):
            audio_data = np.asarray(audio_data, dtype=np.float32)

        start_time = time.time()

        segments, info = self.model.transcribe(
            audio_data,
            beam_size=beam_size,
            language="en",
            condition_on_previous_text=False
        )

        full_text = ""
        for segment in segments:
            full_text += segment.text

        duration = time.time() - start_time
        audio_duration = info.duration
        
        # Calculate Real Time Factor (RTF) = Processing Time / Audio Duration
        # Lower is better. < 1.0 is required for real-time.
        rtf = duration / audio_duration if audio_duration > 0 else 0
        
        if audio_duration > 1.0:
            logger.info(f"STT: '{full_text.strip()}' [RTF: {rtf:.3f}]")
        
        if rtf > 1.0 and audio_duration > 1.5:
            logger.warning(f"HIGH LATENCY ALERT: RTF {rtf:.2f} > 1.0")

        return full_text.strip()
