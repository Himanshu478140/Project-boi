import queue
import threading
import time
import sounddevice as sd
import numpy as np
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AudioInput:
    """
    Threaded Audio Input optimized for Low Latency (WASAPI).
    Captures raw audio in fixed chunks and puts them into a thread-safe queue.
    """
    def __init__(self, sample_rate=16000, chunk_size=512, device_index=None):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size # 512 frames @ 16kHz ~= 32ms
        self.device_index = device_index
        
        self.queue = queue.Queue()
        self.running = False
        self.thread = None
        self.stream = None
        
        # Audio stats
        self.total_chunks_read = 0

    def _callback(self, indata, frames, time_info, status):
        """
        Sounddevice callback. Runs in a separate thread managed by PortAudio/SoundDevice.
        Critical path: Must need be fast.
        """
        if status:
            logger.warning(f"Audio Input Status: {status}")
        
        # DEBUG: Visualize callback life
        # print(".", end="", flush=True) 
        
        # Copy is crucial as 'indata' is reused by sounddevice
        self.queue.put(indata.copy())
        self.total_chunks_read += 1

    def start(self):
        """Starts the audio input stream."""
        if self.running:
            return

        logger.info(f"Starting AudioInput (Device: {self.device_index if self.device_index else 'Default'}, Rate: {self.sample_rate}, Chunk: {self.chunk_size})")
        # Log all devices for debug
        logger.info(f"Available Devices:\n{sd.query_devices()}")
        
        self.running = True
        
        try:
            # We use a callback-based stream which acts as its own thread implicitly,
            # but we wrap the lifecycle management if needed. 
            # sounddevice callback mode is preferred for low latency over blocking read.
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                device=self.device_index,
                channels=1,
                dtype='float32',
                callback=self._callback,
                # latency='low', # REMOVED: Causing issues on some Windows setups
                extra_settings=None 
            )
            self.stream.start()
            logger.info("AudioInput started successfully.")
        except Exception as e:
            logger.error(f"Failed to start AudioInput: {e}")
            self.running = False
            raise

    def stop(self):
        """Stops the audio input stream."""
        logger.info("Stopping AudioInput...")
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        logger.info("AudioInput stopped.")

    def get_chunk(self, timeout=None):
        """
        Retrieves the next audio chunk from the queue.
        Returns: numpy array (float32) or None if timeout/empty.
        """
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear(self):
        """Clears the buffer."""
        with self.queue.mutex:
            self.queue.queue.clear()
