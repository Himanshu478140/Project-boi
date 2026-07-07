import torch
import numpy as np
import logging

logger = logging.getLogger(__name__)

class VADEngine:
    """
    Wrapper for Silero VAD v5.
    Processes audio chunks and returns Speech Probability.
    """
    def __init__(self, threshold=0.5, sampling_rate=16000):
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.model = None
        self.utils = None
        self._load_model()
        
        # State
        self.speech_probability = 0.0

    def _load_model(self):
        try:
            logger.info("Loading Silero VAD Model...")
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            # Use minimal utils
            (self.get_speech_timestamps,
             self.save_audio,
             self.read_audio,
             self.VADIterator,
             self.collect_chunks) = self.utils
             
            self.model.eval()
            logger.info("Silero VAD Loaded successfully.")
        except Exception as e:
            logger.critical(f"Failed to load Silero VAD: {e}")
            raise

    def process_chunk(self, audio_float32):
        """
        Input: numpy array (float32, -1.0 to 1.0)
        Returns: float (speech probability 0.0 to 1.0)
        """
        if self.model is None:
            return 0.0

        # Convert to tensor
        # Silero expects (batch, channel,time) or (channel, time)?
        # Usually requires tensor of shape (1, N) for single channel
        
        # Ensure correct shape and type
        if len(audio_float32.shape) == 1:
            tensor = torch.from_numpy(audio_float32).unsqueeze(0)
        else:
            tensor = torch.from_numpy(audio_float32)
            
        with torch.no_grad():
            try:
                # Silero v5 forward pass returns probability directly for the chunk?
                # Or do we strictly need the VADIterator for state management?
                # Using model(x, sr) is the simple API, but VADIterator is better for streaming
                # Let's use the simple API first for raw probability access
                
                speech_prob = self.model(tensor, self.sampling_rate).item()
                self.speech_probability = speech_prob
                return speech_prob
                
            except Exception as e:
                logger.error(f"VAD Error: {e}")
                return 0.0

    def is_speech(self, audio_float32):
        prob = self.process_chunk(audio_float32)
        return prob > self.threshold
