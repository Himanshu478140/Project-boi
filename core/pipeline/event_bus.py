import logging
import threading
import time
from enum import Enum
from queue import Queue

logger = logging.getLogger(__name__)

class EventType(Enum):
    # External
    USER_SPEECH_DETECTED = "USER_SPEECH_DETECTED"
    USER_SPEECH_FINAL = "USER_SPEECH_FINAL"
    
    # Cognitive / Internal
    INTENT_IDENTIFIED = "INTENT_IDENTIFIED"
    CONFUSION_DETECTED = "CONFUSION_DETECTED"
    EMOTION_INFERRED = "EMOTION_INFERRED"
    TASK_COMPLETED = "TASK_COMPLETED"
    
    # Lifecycle
    RESPONSE_COMMITTED = "RESPONSE_COMMITTED" # Text generated, safe to memorize
    REFLECTION_PHASE = "REFLECTION_PHASE" # Turn over, time to think/proact

class Event:
    def __init__(self, event_type, data=None):
        self.type = event_type
        self.data = data or {}
        self.timestamp = time.time()

class EventBus:
    """
    Central Nervous System for Jarvis.
    Decouples components via Pub/Sub.
    """
    def __init__(self):
        self.listeners = {} # {EventType: [callback_fns]}
        self._queue = Queue()
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def subscribe(self, event_type, callback):
        """
        Register a callback for an event type.
        Callback signature: callback(event_data)
        """
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)
        logger.debug(f"Subscribed to {event_type.name}")

    def publish(self, event_type, data=None):
        """
        Fire and forget. Puts event on the queue.
        """
        event = Event(event_type, data)
        self._queue.put(event)
        # logger.debug(f"Event Published: {event_type.name}")

    def _process_queue(self):
        while self.running:
            try:
                event = self._queue.get()
                self._dispatch(event)
                self._queue.task_done()
            except Exception as e:
                logger.error(f"EventBus Worker Error: {e}")

    def _dispatch(self, event):
        if event.type in self.listeners:
            for callback in self.listeners[event.type]:
                try:
                    # Run callback
                    # Note: This runs in the EventBus worker thread. 
                    # Heavy tasks (like LLM calls) inside callbacks 
                    # should spawn their own threads if they want to be non-blocking 
                    # to *other* listeners, though this bus is already async to the publisher.
                    callback(event.data)
                except Exception as e:
                    logger.error(f"Error in listener for {event.type.name}: {e}")
