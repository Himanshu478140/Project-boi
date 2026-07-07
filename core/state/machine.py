import logging
import threading
from enum import Enum, auto

logger = logging.getLogger(__name__)

class State(Enum):
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()

class StateMachine:
    """
    Deterministic State Machine for the Voice Assistant.
    Thread-safe transitions.
    """
    def __init__(self):
        self._state = State.IDLE
        self._lock = threading.Lock()
        self.listeners = []

    @property
    def current_state(self):
        with self._lock:
            return self._state

    def set_state(self, new_state: State):
        with self._lock:
            if self._state == new_state:
                return
            
            logger.info(f"STATE CHANGE: {self._state.name} -> {new_state.name}")
            self._state = new_state
            
            # Notify listeners (if any)
            for listener in self.listeners:
                try:
                    listener(new_state)
                except Exception as e:
                    logger.error(f"State listener error: {e}")

    def add_listener(self, callback):
        self.listeners.append(callback)
