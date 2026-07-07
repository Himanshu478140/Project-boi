import time
import logging

logger = logging.getLogger(__name__)

class InteractionReflexEngine:
    """
    Manages the 'Social State' of the conversation.
    Decides when to trigger micro-interactions (Active Listening) based on 
    conversation history and timing, ensuring we never nag the user.
    """
    def __init__(self):
        # State
        self.session_start_time = time.time()
        self.session_turn_count = 0
        self.last_user_activity = time.time()
        
        # Flags (One-shot triggers)
        self.has_prompted_presence = False
        self.has_prompted_patience = False # reset per turn
        
        # Config
        self.PRESENCE_TIMEOUT = 15.0 # seconds
        self.PATIENCE_TIMEOUT = 1.8 # seconds (dynamic min)
        
    def on_user_activity(self):
        """Call whenever user speech is detected."""
        self.last_user_activity = time.time()
        # Note: We don't increment turn count here, only on commit
        
    def on_turn_commit(self):
        """Call when a turn is fully processed."""
        self.session_turn_count += 1
        self.has_prompted_patience = False # Reset for next turn
        
    def check_presence_prompt(self, current_state_is_listening):
        """
        Should we ask 'Are you there?'
        Constraint: Only if LISTENING, Silence > 15s, Turn Count == 0 (Start of session only).
        """
        if not current_state_is_listening:
            return False
            
        if self.has_prompted_presence:
            return False
            
        if self.session_turn_count > 0:
            return False # User has engaged, no need to nag
            
        elapsed = time.time() - self.last_user_activity
        if elapsed > self.PRESENCE_TIMEOUT:
            self.has_prompted_presence = True
            return True
            
        return False

    def check_patience_prompt(self, is_incomplete, silence_duration):
        """
        Should we say 'Take your time'?
        Constraint: Incomplete text, Silence > Threshold, Not yet prompted this turn.
        """
        if not is_incomplete:
            return False
            
        if self.has_prompted_patience:
            return False
            
        if silence_duration > self.PATIENCE_TIMEOUT:
            self.has_prompted_patience = True
            return True
            
        return False
