import queue
import threading
import sounddevice as sd
import numpy as np
import logging
import time

logger = logging.getLogger(__name__)

class AudioOutput:
    """
    Threaded Audio Output with Immediate Interruption.
    Plays audio chunks from a queue.
    """
    def __init__(self, sample_rate=24000, device_index=None):
        self.sample_rate = sample_rate # Kokoro/Piper likely 24k or 22.05k
        self.device_index = device_index
        
        self.queue = queue.Queue()
        self.running = False
        self.thread = None
        self.stream = None
        self.interrupted = threading.Event()
        self.is_playing_flag = False

    def start(self):
        if self.running:
            return
            
        self.running = True
        self.interrupted.clear()
        
        # Start the playback worker thread
        self.thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.thread.start()
        logger.info("AudioOutput thread started.")

    def _playback_loop(self):
        """
        Blocking playback loop. 
        """
        try:
            with sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                device=self.device_index,
                latency='low' 
            ) as stream:
                self.stream = stream
                
                while self.running:
                    try:
                        # Wait for data
                        try:
                            # Queue item: (chunk_np_array, volume_gain_float)
                            item = self.queue.get(timeout=0.1)
                            
                            if isinstance(item, tuple):
                                chunk, gain = item
                            else:
                                chunk, gain = item, 1.0 # Backwards compat
                                
                        except queue.Empty:
                            self.is_playing_flag = False
                            continue

                        # Check interruption
                        if self.interrupted.is_set():
                            self._drain_queue()
                            self.interrupted.clear()
                            self.is_playing_flag = False
                            continue

                        self.is_playing_flag = True
                        
                        # Process Chunk
                        # 1. Ensure float32
                        if chunk.dtype != np.float32:
                            chunk = chunk.astype(np.float32)
                            
                        # 2. Apply Gain
                        if gain != 1.0:
                            chunk = chunk * gain
                            
                        # 3. Apply Fades (Basic Heuristic: If chunk long enough, micro-fade edges to avoid clicks)
                        # More complex fading is handled by Prosody Engine pre-processing or explicit fade flags if needed.
                        # For now, we rely on the input chunk being "clean", but we can add a tiny 5ms fade to avoid clicks if gain changed.
                        # (Skipping complex fade logic here for latency, assuming TTS chunks are windowed)

                        stream.write(chunk)
                        
                    except Exception as e:
                        logger.error(f"Playback error: {e}")
                        
        except Exception as e:
            logger.critical(f"AudioOutput stream failed: {e}")
            self.running = False

    def play_chunk(self, chunk, volume_gain=1.0):
        """
        Adds a chunk to the playback queue.
        volume_gain: Float 0.0 to 1.5
        """
        self.queue.put((chunk, volume_gain))

    def stop_immediate(self):
        """
        CRITICAL: Triggers immediate interruption.
        """
        logger.info("STOP IMMEDIATE TRIGGERED")
        self.interrupted.set()
        self._drain_queue()

    def _drain_queue(self):
        try:
            while True:
                self.queue.get_nowait()
        except queue.Empty:
            pass

    def is_playing(self):
        return self.is_playing_flag or not self.queue.empty()

    def shutdown(self):
        self.running = False
        self.stop_immediate()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
