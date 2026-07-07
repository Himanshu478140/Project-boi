import logging
import collections

logger = logging.getLogger(__name__)

class MemoryEngine:
    """
    Manages short-term conversation history using a FIFO Sliding Window.
    Prioritizes recency over everything else.
    """
    
    def __init__(self, max_turns=10):
        # max_turns = count of User+Assistant pairs.
        # So actual max messages = max_turns * 2
        self.max_messages = max_turns * 2 
        self.history = []

    def add(self, role, content):
        """
        Add a message to history.
        role: "user" or "assistant"
        content: text string
        """
        if not content or not content.strip():
            return

        message = {"role": role, "content": content}
        self.history.append(message)
        self._prune()

    def get_history(self):
        """
        Return list of message dicts.
        """
        return self.history

    def clear(self):
        """
        Wipe conversation history.
        """
        self.history = []
        logger.info("Memory Cleared.")

    def _prune(self):
        """
        Enforce FIFO limit. remove oldest messages.
        """
        if len(self.history) > self.max_messages:
            # Remove oldest
            excess = len(self.history) - self.max_messages
            self.history = self.history[excess:]
            # logger.debug(f"Memory Pruned: Removed {excess} old messages.")
