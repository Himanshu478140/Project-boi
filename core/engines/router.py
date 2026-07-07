
import logging
from enum import Enum, auto

logger = logging.getLogger(__name__)

class Route(Enum):
    SOCIAL = auto()   # Talker/Chat Mode
    PLANNER = auto()  # Deep Reasoning
    JARVIS = auto()   # System/Action/Vision Mode

class Router:
    """
    Deterministic routing layer between STT and LLM.
    Decides whether to use the Fast Path (Talker), Slow Path (Planner), or Vision Path.
    """
    
    # Heuristic Configuration
    
    # JARVIS Signals (Action / Vision / System)
    JARVIS_KEYWORDS = [
        "look at", "see", "watch", "read this", "what is on my screen", 
        "check this", "visualize", "scan", "take a screenshot", "capture",
        "monitor", "desktop", "system", "app", "window"
    ]

    # SOCIAL Signals (Conversational / Greeting)
    SOCIAL_KEYWORDS = [
        "hello", "hi", "hey", "how are you", "thanks", "thank you", 
        "good morning", "good evening", "joke", "story"
    ]
    
    # PLANNER Signals (Complex Reasoning)
    PLANNER_KEYWORDS = [
        "plan", "design", "code", "write", "solve", "explain", "compare", 
        "list", "generate", "create", "analyze", "program", "debug",
        "difference between", "how do", "why"
    ]
    
    LENGTH_THRESHOLD_WORDS = 25 
    
    @staticmethod
    def route(text):
        """
        Input: Finalized STT Transcript.
        Output: Route.SOCIAL, Route.PLANNER, or Route.JARVIS
        """
        if not text:
            # Default to JARVIS (Observation) or SOCIAL? 
            # If silent, we usually don't route, but purely reactive default is SOCIAL
            return Route.SOCIAL
            
        clean_text = text.strip().lower()
        words = clean_text.split()
        word_count = len(words)
        
        # 1. JARVIS Check (System/Vision) - Highest Priority
        if any(k in clean_text for k in Router.JARVIS_KEYWORDS):
            logger.info("Router: JARVIS (System/Vision Intent)")
            return Route.JARVIS

        # 2. SOCIAL Check (Explicit Conversational)
        if any(k in clean_text for k in Router.SOCIAL_KEYWORDS):
            # Check for mixed intents ("Hi, write code") -> Planner
            if not any(k in clean_text for k in Router.PLANNER_KEYWORDS):
                logger.info("Router: SOCIAL (Conversational Intent)")
                return Route.SOCIAL

        # 3. PLANNER Check (Deep Work)
        # Length check for complex queries
        if word_count > Router.LENGTH_THRESHOLD_WORDS:
            logger.info(f"Router: PLANNER (Length {word_count} > {Router.LENGTH_THRESHOLD_WORDS})")
            return Route.PLANNER
            
        if any(k in clean_text for k in Router.PLANNER_KEYWORDS):
            logger.info("Router: PLANNER (Strong Keyword)")
            return Route.PLANNER
            
        # 4. Ambiguity Resolution
        if clean_text.startswith("what is") or clean_text.startswith("who is"):
             if word_count > 6:
                 return Route.PLANNER
             else:
                 return Route.SOCIAL # "What is the time?"
                 
        # Default
        logger.info("Router: SOCIAL (Default Fallback)")
        return Route.SOCIAL
