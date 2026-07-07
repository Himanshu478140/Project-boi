import logging
import ollama
from core.engines.vision_engine import VisionEngine

logger = logging.getLogger(__name__)

class LocalVisionEngine:
    def __init__(self, model="llava-phi3"):
        self.vision = VisionEngine()
        self.model = model
        self.last_analysis = ""

    def analyze_screen(self, prompt="Describe what is on the screen in 10 words. Focus on the active application."):
        """
        Captures screen and sends to Local LLM (Ollama).
        Returns text description.
        """
        try:
            # 1. Capture (Base64)
            # Use monitor 1 default
            base64_img = self.vision.capture_screen()
            if not base64_img:
                return None

            # 2. Query Ollama
            # Moondream is fast.
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': [base64_img]
                    }
                ],
                keep_alive=0 # Free VRAM immediately after use (prevent conflict with TTS/LLM)
            )
            
            result = response['message']['content']
            self.last_analysis = result
            return result

        except Exception as e:
            logger.error(f"Local Vision Analysis Failed: {e}")
            return None