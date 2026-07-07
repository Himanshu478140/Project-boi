
import logging
import threading
import time
import numpy as np
import copy
from core.engines.stt_engine import STTEngine

logger = logging.getLogger(__name__)

class StreamingSTT:
    """
    Pseudo-Streaming STT wrapper.
    Accumulates audio and periodically re-transcribes the growing buffer
    to provide "live" partial results.
    """
    def __init__(self, stt_engine: STTEngine, callback=None):
        self.stt = stt_engine
        self.callback = callback # Function(text, is_final)
        
        self.buffer = []
        self.last_inference_time = 0
        self.is_running = False
        
        # Stability tracking
        self.last_partial_text = ""
        self.stability_count = 0
        self.stable_text_len = 0
        
        # Config
        self.MIN_INTERVAL = 0.25 # Basic refresh rate (250ms)
        self.MIN_AUDIO_LEN = 0.5 # Wait for at least 0.5s before first guess
        
        # Thread safety
        self.lock = threading.Lock()
        self.inference_lock = threading.Lock()

    def process_chunk(self, chunk):
        """
        Ingest small audio chunk from VAD/Input.
        Non-blocking.
        """
        with self.lock:
            self.buffer.append(chunk)
            
        # Check if we should run inference
        now = time.time()
        if (now - self.last_inference_time) > self.MIN_INTERVAL:
            # Fire and forget inference thread
            if not self.inference_lock.locked():
                 threading.Thread(target=self._run_inference, daemon=True).start()

    def _run_inference(self):
        """
        Runs STT on the current buffer snapshot.
        """
        if not self.inference_lock.acquire(blocking=False):
            return

        try:
            # Snapshot the buffer
            with self.lock:
                if not self.buffer:
                    return
                # Copy current buffer state
                current_audio = np.concatenate(self.buffer)
                
            duration = len(current_audio) / 16000
            if duration < self.MIN_AUDIO_LEN:
                return

            self.last_inference_time = time.time()
            
            # Run STT (Greedy is fine for partials)
            text = self.stt.transcribe(current_audio, beam_size=1)
            text = text.strip()
            
            # --- STABILITY LOGIC (Anti-Hallucination) ---
            # If text is same as last time, increment stability count.
            # If text changed, reset count.
            
            if text == self.last_partial_text:
                self.stability_count += 1
            else:
                self.stability_count = 0
                self.last_partial_text = text
            
            # Trust Threshold:
            # 0.5s audio -> 2 matches needed?
            # We want to filter out "Hi, how will you do" flickering.
            
            # Simple heuristic:
            # If length < 10 chars, require 2 stable cycles (3 total hits)
            # If length > 10 chars, require 1 stable cycle (2 total hits)
            
            if len(text) < 10:
                 is_stable = self.stability_count >= 2
            else:
                 is_stable = self.stability_count >= 1
            
            if self.callback:
                # EMIT PARTIAL
                # We emit always, but Orchestrator can use stability_count if exposed,
                # or we append a flag.
                # For backward compat, we just callback text.
                self.callback(text, is_final=False)

        except Exception as e:
            logger.error(f"Streaming STT Error: {e}")
        finally:
            self.inference_lock.release()

    def is_stable(self):
        """Returns True if the current partial has persisted for >1 inference cycle."""
        return self.stability_count >= 1

    def get_current_text(self):
        """Thread-safe access to latest partial."""
        return self.last_partial_text

    def commit(self):
        """
        Called when VAD confirms End-of-Turn.
        Returns the final text and clears buffer.
        """
        with self.lock:
            if not self.buffer:
                return ""
            final_audio = np.concatenate(self.buffer)
            self.buffer = [] # CLEAR BUFFER
            last_text = self.last_partial_text
            self.last_partial_text = ""
        
        # OPTIMIZATION: If partial inference ran recently (< 0.5s ago) and yielded text, 
        # trust it to avoid re-running the heavy model.
        # This saves ~300-500ms of latency at the end of every turn.
        now = time.time()
        if last_text and (now - self.last_inference_time) < 0.6:
            logger.info(f"StreamingSTT: Reusing recent partial '{last_text}' (Latency Saved)")
            if self.callback:
                self.callback(last_text, is_final=True)
            return last_text

        # Otherwise, run one final high-quality pass
        logger.info("Committing Final Transcript (Full Pass)...")
        text = self.stt.transcribe(final_audio, beam_size=1)
        if self.callback:
            self.callback(text, is_final=True)
            
        return text

    def reset(self):
        """
        Clears the buffer without transcribing.
        Used when the turn is rejected (e.g. noise).
        """
        with self.lock:
            self.buffer = []
            self.last_partial_text = ""
