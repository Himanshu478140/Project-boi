import logging
import json

logger = logging.getLogger(__name__)

class MemoryIntegrator:
    """
    The 'Subconscious' that runs in the background.
    Analyzes conversation turns to extract long-term facts.
    """
    def __init__(self, profile_manager, llm_engine):
        self.profile = profile_manager
        self.llm = llm_engine

    def process_turn(self, user_text, assistant_text):
        """
        Analyzes the last turn for new facts.
        """
        if not user_text or len(user_text) < 5:
            return

        try:
            # check if we should even bother (simple keyword filter to save tokens?)
            # nah, let the LLM decide. It's cheap enough.
            
            prompt = f"""
            Task: Extract PERMANENT FACTS about the USER from the conversation.
            
            User said: "{user_text}"
            Assistant said: "{assistant_text}"
            
            Instructions:
            - Extracts facts like: "User is a Python developer", "User hates bugs", "User name is Dan".
            - Ignore temporary state (e.g., "I am hungry now").
            - Ignore questions (e.g., "What is the time?").
            - If NO new permanent facts: Output JSON {{ "fact": null }}
            - If YES: Output JSON {{ "fact": "The extracted fact string" }}
            """
            
            response = self.llm.generate_oneshot(
                system_prompt="You are a facts extractor. Output JSON.",
                user_prompt=prompt,
                model="gpt-4o-mini", # Fast model is fine for this
                response_format={"type": "json_object"}
            )
            
            data = json.loads(response)
            fact = data.get("fact")
            
            if fact:
                logger.info(f"Subconscious extracted fact: '{fact}'")
                saved = self.profile.remember_fact(fact)
                if saved:
                    logger.info("Fact saved to Long-Term Memory.")
                else:
                    logger.info("Fact already known.")

        except Exception as e:
            logger.error(f"Memory Integration Failed: {e}")
