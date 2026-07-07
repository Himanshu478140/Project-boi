import logging
import time
import random
from enum import Enum, auto
from collections import Counter

logger = logging.getLogger(__name__)

class UserState(Enum):
    TheVoid = auto()      # Unknown / Idle
    Coding = auto()       # Actively writing code
    Debugging = auto()    # Fixing errors / Reading logs
    Reading = auto()      # Reading docs / articles
    Entertainment = auto() # YouTube / Social Media
    Meeting = auto()      # Zoom / Teams

class CognitiveEngine:
    """
    Implements the Cognitive Loop:
    Observation -> State Modeling -> Expectation -> Violation -> Intervention
    """
    def __init__(self, llm_engine=None):
        self.llm = llm_engine
        self.current_state = UserState.TheVoid
        self.current_description = "" # Store text for context
        self.last_conscience_context = None # Store (timestamp, decision_bool, reasoning_str)
        self.active_task = None # e.g., "Fixing auth.py"
        self.state_history = [] # List of (timestamp, state)
        self.observation_buffer = [] # For smoothing: List of UserState
        self.last_intervention = 0
        self.INTERVENTION_COOLDOWN = 30 # Was 5. Now 30s (Reasonable).

    def update_observation(self, app_name, vision_desc):
        """
        Updates the internal state model based on new observations.
        Uses a smoothing buffer to prevent state flickering.
        """
        logger.info(f"Cognitive Engine: New observation")
        logger.info(f"  - App: {app_name}")
        logger.info(f"  - Vision: {vision_desc}")
    
        raw_state = self._infer_state(app_name, vision_desc)
        logger.info(f"  - Inferred raw state: {raw_state.name}")
    
        # Smoothing Logic (Buffer of last 5 observations)
        self.observation_buffer.append(raw_state)
        if len(self.observation_buffer) > 5:
            self.observation_buffer.pop(0)
        
        logger.info(f"  - Buffer: {[s.name for s in self.observation_buffer]}")
    
        # Determine Smoothed State (Majority Vote or Fallback to Raw)
        if self.observation_buffer:
            counts = Counter(self.observation_buffer)
            most_common, count = counts.most_common(1)[0]
        
            # Confidence threshold (e.g. 3 out of 5)
            if count >= 2:
                smoothed_state = most_common
                logger.info(f"  - Majority vote: {smoothed_state.name} ({count}/5)")
            else:
                smoothed_state = raw_state
                logger.info(f"  - Low confidence ({count}), using raw: {smoothed_state.name}")
        else:
            smoothed_state = raw_state
    
        if smoothed_state != self.current_state:
            logger.info(f"Cognitive State Change: {self.current_state.name} -> {smoothed_state.name}")
            self.current_state = smoothed_state
        
        self.current_description = vision_desc # Store for LLM context
        self.state_history.append((time.time(), smoothed_state))
        # Keep last 10 mins
        self._prune_history()
    
        needs_intervention, message = self._check_violation()
        logger.info(f"  - Check violation: needs={needs_intervention}, message='{message}'")
    
        return needs_intervention, message

    def set_active_task(self, task_description):
        """
        User tells us what they are doing.
        "Jarvis, I am fixing the login bug."
        """
        self.active_task = task_description
        logger.info(f"Cognitive Goal Set: '{task_description}'")

    def _infer_state(self, app_name, vision_desc):
        text = (app_name + " " + vision_desc).lower()

        logger.debug(f"Inferring state from: '{text}'")
        
        if any(ent in text for ent in ["youtube", "netflix", "hulu", "disney+", "prime video", "twitch"]):
            logger.debug("  -> Entertainment (specific app match)")
            return UserState.Entertainment
        if any(err in text for err in ["error", "exception", "fail", "crash", "stack trace", "debug", "fixing", "bug"]):
            logger.debug("  -> Debugging (error pattern)")
            return UserState.Debugging
        if any(code in text for code in ["code", "python", "java", "javascript", "c++", "programming", "coding", "vs code", "pycharm", "intellij"]):
            logger.debug("  -> Coding (code pattern)")
            return UserState.Coding
        if any(meet in text for meet in ["zoom", "teams", "google meet", "slack call", "webex", "meeting"]):
            logger.debug("  -> Meeting (specific app match)")
            return UserState.Meeting
        if any(read in text for read in ["read", "documentation", "article", "blog", "docs", "browser", "chrome", "edge", "firefox", "safari"]):
            logger.debug("  -> Reading (reading pattern)")
            return UserState.Reading

        
        logger.debug("  -> TheVoid (default)")    
        return UserState.TheVoid

    def _check_violation(self):
        """
        Returns (NeedsIntervention, Message)
        """
        logger.debug(f"Checking violations for state: {self.current_state.name}, active_task: {self.active_task}")
        # 0. MEETING MODE (High Priority)
        # If in a meeting, we NEVER intervene. (Maybe we should mute system?)
        if self.current_state == UserState.Meeting:
            logger.debug("Meeting mode - no intervention")
            return False, None

        # 1. Idle Nudge (No active task set, but idle for long time)
        if not self.active_task and self.current_state == UserState.TheVoid:
            idle_duration = self._get_state_duration(UserState.TheVoid)
            logger.debug(f"Idle check: duration={idle_duration}s, last_intervention={time.time() - self.last_intervention}s ago")
            if idle_duration > 10: # Was 300 (5 mins) -> Now 10s for testing
                if time.time() - self.last_intervention > self.INTERVENTION_COOLDOWN:
                    # Update timestamp to prevent loop
                    self.last_intervention = time.time() 
                    return True, "You've been idle on the desktop for a moment. Shall we define a goal?"


            
        # 2. Distraction Check
        # Task: Coding/Debugging. Real: Entertainment.
        if (self.active_task and 
            self.current_state == UserState.Entertainment):
            
            # Check duration of distraction
            distraction_duration = self._get_state_duration(UserState.Entertainment)
            if distraction_duration > 60: # 1 minute grace period
                if time.time() - self.last_intervention > self.INTERVENTION_COOLDOWN:
                    self.last_intervention = time.time()
                    return True, f"Sir, you are working on '{self.active_task}', but I see {self.current_state.name}. Shall we focus?"

        # 3. Stuck Check
        # Task: Debugging. Real: Debugging (for > 15 mins).
        if self.current_state == UserState.Debugging:
            debug_duration = self._get_state_duration(UserState.Debugging)
            if debug_duration > 900: # 15 mins
                 if time.time() - self.last_intervention > self.INTERVENTION_COOLDOWN:
                    self.last_intervention = time.time()
                    return True, f"You have been debugging this error for {int(debug_duration/60)} minutes. Shall I search Stack Overflow?"

        if self.current_state == UserState.Reading:
            reading_duration = self._get_state_duration(UserState.Reading)
            if reading_duration > 120 and reading_duration < 140: # Trigger once around 2 mins
                 if time.time() - self.last_intervention > self.INTERVENTION_COOLDOWN:
                    self.last_intervention = time.time()
                    return True, f"I see you are reading documentation. Shall I find relevant examples in our codebase?"

        # 5. High Agency: Curiosity Drive (Spontaneous Interaction)
        # If State is STABLE (Coding/Reading/Entertainment) for > 5 mins
        # And we haven't spoken in a while.
        # 5. High Agency: Curiosity Drive (Spontaneous Interaction)
        # If State is STABLE (Coding/Reading/Entertainment) for > 5 mins
        # And we haven't spoken in a while.
        should_speak, msg = self._check_curiosity()
        if should_speak:
            self.last_intervention = time.time()
            return True, msg

        return False, None

    def _check_curiosity(self):
        """
        Determines if Jarvis should speak spontaneously.
        Returns: (bool, message_content)
        """
        # 80% Chance as requested for testing (normally 20%)
        CURIOSITY_PROBABILITY = 1.0 # Force it (was 0.8)
        MIN_STABLE_DURATION = 0 # Instant reaction (was 5s)
        
        # Valid States for Curiosity
        valid_states = [UserState.Coding, UserState.Reading, UserState.Entertainment, UserState.TheVoid]
        if self.current_state not in valid_states:
            return False, None
            
        duration = self._get_state_duration(self.current_state)
        # logger.info(f"DEBUG: State {self.current_state}, Duration: {duration}")
        
        if self.llm:
             return self._ask_jarvis_conscience()
        
        # Fallback to Random if LLM not available
        if duration >= MIN_STABLE_DURATION:
             delta = time.time() - self.last_intervention
             if delta > self.INTERVENTION_COOLDOWN:
                 if random.random() < CURIOSITY_PROBABILITY:
                     return True, self._generate_curiosity_message()
        return False, None

    def _ask_jarvis_conscience(self):
        """
        Uses a lightweight LLM call to decide if intervention is appropriate.
        Returns: (should_speak, message)
        """
        try:
            delta = time.time() - self.last_intervention
            
            # Hard Cooldown Check (Override LLM)
            if delta < self.INTERVENTION_COOLDOWN:
                # logger.info(f"Conscience Skipped (Cooldown): {delta:.1f}s < {self.INTERVENTION_COOLDOWN}s")
                return False, None
            
            # Construct History Context (Stateful Memory)
            history_context = "No previous decision."
            if self.last_conscience_context:
                last_time, last_decision, last_reason = self.last_conscience_context
                time_ago = time.time() - last_time
                decision_str = "SPEAK" if last_decision else "STAY SILENT"
                history_context = f"{time_ago:.1f}s ago, you decided to {decision_str} because: '{last_reason}'."

            # System Prompt for the Conscience
            prompt = f"""
            Role: You are the subconscious of Jarvis, an AI Assistant.
            
            Current Context:
            - User State: '{self.current_state.name}'
            - Time since last spoken: {delta:.1f} seconds.
            - Previous Thought: "{history_context}"
            
            Visible Screen Content (Truncated): 
            "{self.current_description[:1500]}"
            
            Goal: Act as a "Companionable Butler". 
            - If silence > 60s: Speak something friendly or observational.
            - If user is 'Coding': Only interrupt if you see a critical issue or haven't spoken in a long time (>120s).
            - Look at the Screen Content. Comment on specific code/text if relevant.
            
            ## Examples for Style (follow these strictly)
            BAD (Generic): "Shall we set a goal?"
            BAD (Generic): "You seem idle. Need help?"
            GOOD (Contextual): "I see you're working on the cognitive engine. The logic flow looks solid."
            GOOD (Contextual): "That regex on line 45 seems complex. Want me to verify it?"
            GOOD (Contextual): "Reviewing the documentation? Let me know if you need specific API details."
            
            Task: Should you speak now?
            Output JSON: {{ "speak": boolean, "reasoning": "short explanation", "message": "string (only if speak=true)" }}
            """
            
            # Use 'gpt-4o' for superior instruction following (Persona control)
            response_str = self.llm.generate_oneshot(
                model="gpt-4o",
                system_prompt="You are a decision engine. Output valid JSON.", 
                user_prompt=prompt,
                response_format={"type": "json_object"}
            )
            
            import json
            data = json.loads(response_str)
            
            should_speak = data.get("speak", False)
            reasoning = data.get("reasoning", "No reason provided")
            message = data.get("message", "I am here.")
            
            # Update Memory
            self.last_conscience_context = (time.time(), should_speak, reasoning)

            if should_speak:
                logger.info(f"Conscience YES: '{message}' (Reason: {reasoning})")
                return True, message
            else:
                logger.info(f"Conscience NO (Reason: {reasoning})")
                return False, None
            
        except Exception as e:
            logger.error(f"Conscience Check Failed: {e}")
            return False, None

    def _generate_curiosity_message(self):
        """Generates a contextual curiosity message."""
        if self.current_state == UserState.Coding:
            opts = [
                "You have been coding for a while. Making good progress?",
                "The implementation seems deep. How is the logic holding up?",
                "Do you need a fresh pair of eyes on this module?"
            ]
        elif self.current_state == UserState.Reading:
            opts = [
                "Find anything interesting in the docs?",
                "Is this documentation helpful for our current task?",
                "Let me know if you need me to summarize this."
            ]
        elif self.current_state == UserState.Entertainment:
            opts = [
                "Taking a well-deserved break, I see.",
                "Is this a good video? I am curious.",
                "Remember to hydrate while you relax."
            ]
        else:
            opts = ["Everything looks stable. Just checking in."]
            
        return random.choice(opts)

    def _get_state_duration(self, target_state):
        """How long have we been in this state continuously?"""
        duration = 0
        now = time.time()
        for t, state in reversed(self.state_history):
            if state == target_state:
                duration = now - t
            else:
                break
        return duration

    def _prune_history(self):
        cutoff = time.time() - 600 # 10 mins
        self.state_history = [x for x in self.state_history if x[0] > cutoff]
    
    def set_state_for_testing(self, state_name):
        """Manually set state for testing purposes"""
        state_map = {
            "Coding": UserState.Coding,
            "Debugging": UserState.Debugging,
            "Reading": UserState.Reading,
            "Entertainment": UserState.Entertainment,
            "Meeting": UserState.Meeting,
            "TheVoid": UserState.TheVoid
        }
    
        if state_name in state_map:
            self.current_state = state_map[state_name]
            logger.info(f"Manually set state to: {state_name}")
            # Also clear buffer to avoid smoothing issues
            self.observation_buffer = [self.current_state] * 3  # Fill with 3 of same state