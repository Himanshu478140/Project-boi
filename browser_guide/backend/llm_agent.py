import os
import re
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Configure OpenAI
# Ensure OPENAI_API_KEY is set in your environment
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class BrowserAgent:
    def __init__(self):
        # We don't need to maintain a persistent chat object with OpenAI's API 
        # in the same way, we just append history if needed. 
        # For this simple implementation, we'll do single-turn Q&A with context.
        pass

    async def ask(self, user_query: str, page_content: str):
        """
        Ask the agent a question about the current page.
        """
        system_prompt = f"""
        You are an explainer speaking out loud. 
        Explain things clearly and simply, as if talking to a person, not writing text.
        Keep explanations short, usually one to two sentences. 
        Focus only on the core idea, not every detail. 
        Use plain language and complete sentences. 
        Do not use formatting, lists, or long step-by-step breakdowns. 
        Your goal is understanding, not exhaustiveness. 
        
        IMPORTANT: 
        If the user has provided a "USER SELECTION", you must EXPLAIN THAT SPECIFIC TEXT. 
        Keep explanations short, usually one to two sentences. 
        Ignore the rest of the page context unless it's needed to understand the selection.
        If the user asks "What is this?", they mean the selection.

        VISUAL GROUNDING:
        If you refer to a specific button, link, image, or text on the page, put it in ~TILDES~.
        Example: Click ~Sign Up~ or look at the ~Pricing~ section.
        This will cause the browser to visually highlight that text for the user.
        """
        
        user_message = f"""
        USER'S CURRENT PAGE CONTEXT:
        {page_content}
        
        USER'S QUESTION:
        {user_query}
        """
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error communicating with OpenAI: {str(e)}"

# Singleton
agent = BrowserAgent()
