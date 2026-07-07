import logging
import os
from openai import OpenAI
from core.config.prompts import SYSTEM_PROMPT_SOCIAL

logger = logging.getLogger(__name__)

class LLMEngine:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set. LLM will fail.")
        
        self.client = OpenAI(api_key=self.api_key)
        # Default to Social prompt if none specified
        self.default_system_prompt = SYSTEM_PROMPT_SOCIAL

    def generate_stream(self, messages, model="gpt-4o-mini"):
        """
        Yields text chunks from OpenAI.
        messages: List of dicts [{"role": "user", "content": ...}, ...]
        """
        try:
            stream = self.client.chat.completions.create(
                model=model, 
                messages=messages,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"OpenAI Error: {e}")
            yield f"I encountered an error: {e}"

    def generate_oneshot(self, system_prompt, user_prompt, model="gpt-4o-mini", **kwargs):
        """
        Non-streaming generation for internal thought processes.
        Supports kwargs for parameters like response_format.
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False,
                **kwargs
            )
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI Oneshot Error: {e}")
            return "NO" # Default safe fallback
