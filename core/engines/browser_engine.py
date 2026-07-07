import logging
import asyncio
import threading
import json
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class BrowserEngine:
    """
    Embedded Browser Integration Engine.
    Hosts a WebSocket server to communicate with the Chrome Extension.
    """
    def __init__(self, host="localhost", port=8000):
        self.host = host
        self.port = port
        self.active_websocket: WebSocket | None = None
        self.latest_page_content: str | None = None
        self.last_update_time = 0
        self.is_running = False
        self.loop = None # Capture the uvicorn loop here
        
        # FastAPI App
        
        # FastAPI App
        self.app = FastAPI()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._setup_routes()
        
    def _setup_routes(self):
        @self.app.websocket("/ws/client")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websocket = websocket
            self.loop = asyncio.get_running_loop() # Capture loop for external scheduling
            logger.info(f"Browser Extension Connected! (Loop captured: {id(self.loop)})")
            
            
            try:
                # Initial content fetch
                await self.send_message("get_content", {})
                
                while True:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await self._handle_message(message)
                    
            except WebSocketDisconnect:
                logger.warning("Browser Extension Disconnected")
                self.active_websocket = None
                self.latest_page_content = None
            except Exception as e:
                logger.error(f"WebSocket Error: {e}")
                self.active_websocket = None
                
    async def _handle_message(self, message):
        msg_type = message.get("type")
        payload = message.get("payload")
        
        if msg_type in ["page_content", "page_content_push"]:
            # Sanitize and truncate
            if isinstance(payload, str):
                self.latest_page_content = payload[:8000] # Safe limit
                self.last_update_time = time.time()
                # logger.debug(f"Updated Browser Content ({len(self.latest_page_content)} chars)")
            elif isinstance(payload, dict):
                 # Handle complex payload if needed
                 pass

    async def send_message(self, type_str, payload):
        if self.active_websocket:
            try:
                await self.active_websocket.send_json({
                    "type": type_str,
                    **payload
                })
                return True
            except Exception as e:
                logger.error(f"Send Failed: {e}")
                return False
        return False

    def get_content(self):
        """Returns the current page context or None if stale/disconnected."""
        if not self.active_websocket:
            return None
        return self.latest_page_content

    async def highlight(self, text: str):
        """Send highlight command to browser."""
        if not text or not self.active_websocket:
            return
            
        logger.info(f"Highlighting in Browser: '{text}'")
        await self.send_message("highlight", {"text": text})

    async def click(self, target_text: str):
        """Send click command to browser."""
        if not target_text or not self.active_websocket:
             logger.warning("Browser Click Failed: No text or no connection.")
             return False
             
        logger.info(f"Clicking in Browser: '{target_text}'")
        await self.send_message("click", {"target": target_text})
        return True

    async def type_text(self, target_text: str, content: str):
        """Send type command to browser."""
        if not target_text or not self.active_websocket:
             return False
             
        logger.info(f"Typing in Browser: '{content}' into '{target_text}'")
        await self.send_message("type", {"target": target_text, "content": content})
        return True

    async def scroll(self, direction: str):
        """Send scroll command (up/down)."""
        if not self.active_websocket:
            return False
            
        logger.info(f"Scrolling Browser: {direction}")
        await self.send_message("scroll", {"direction": direction})
        return True

    async def extract_table(self):
        """Request table extraction from browser."""
        if not self.active_websocket:
            return False
        
        logger.info("Requesting Table Extraction...")
        await self.send_message("table", {})
        return True

    async def navigate(self, url: str):
        if not self.active_websocket: return False
        logger.info(f"Navigating to {url}")
        await self.send_message("goto", {"url": url})
        return True

    async def back(self):
        if not self.active_websocket: return False
        logger.info("Navigating Back")
        await self.send_message("back", {})
        return True

    async def reload(self):
        if not self.active_websocket: return False
        logger.info("Reloading Page")
        await self.send_message("reload", {})
        return True

    async def fill_form(self, data: dict):
        if not self.active_websocket: return False
        logger.info(f"Filling Form with {len(data)} fields")
        await self.send_message("fill_form", {"formData": data})
        return True

    def start(self):
        """Start the Uvicorn server in a separate daemon thread."""
        if self.is_running:
            return
            
        self.is_running = True
        
        def run_server():
            # Disable Uvicorn's own signal handlers to play nice with Main thread
            config = uvicorn.Config(app=self.app, host=self.host, port=self.port, log_level="warning")
            server = uvicorn.Server(config)
            server.run()
            
        t = threading.Thread(target=run_server, daemon=True)
        t.start()
        logger.info(f"BrowserEngine Server started at ws://{self.host}:{self.port}/ws/client")

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    engine = BrowserEngine()
    engine.start()
    try:
        while True:
            time.sleep(1)
            content = engine.get_content()
            if content:
                print(f"Content: {content[:50]}...")
    except KeyboardInterrupt:
        pass
