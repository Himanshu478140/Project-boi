from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from llm_agent import agent
import threading
import sys
import re
from contextlib import asynccontextmanager
from pydantic import BaseModel

# Terminal Request Queue (Thread-safe communication)
import queue
terminal_queue = queue.Queue()

class ConnectionManager:
    def __init__(self):
        self.active_connection: WebSocket = None
        self.latest_page_content: str = "No page loaded yet."
        self.last_update_time: float = 0.0

    async def connect(self, websocket: WebSocket):
        # Accept connection from any origin
        await websocket.accept()
        self.active_connection = websocket
        print("✅ Extension Connected!")
        print("📝 Type questions below (type 'quit' to exit):")

    def disconnect(self, websocket: WebSocket):
        self.active_connection = None
        print("❌ Extension Disconnected")

    async def send_message(self, message_type: str, data: dict):
        """Send a message to the connected WebSocket client"""
        if self.active_connection:
            try:
                message = {"type": message_type, **data}
                await self.active_connection.send_text(json.dumps(message))
                return True
            except Exception as e:
                print(f"❌ Error sending message: {e}")
                return False
        else:
            print("⚠️ No active connection to send message")
            return False

    def update_content(self, content: str):
        self.latest_page_content = content
        self.last_update_time = asyncio.get_event_loop().time()
        print(f"📄 Updated Page Content: {len(content)} chars")

        if content and len(content) > 50:
            preview = content[:100].replace('\n', ' ')
            print(f"📋 Preview: {preview}...")

manager = ConnectionManager()

# Background task to process terminal queue
async def process_terminal_queue():
    while True:
        if not terminal_queue.empty():
            question = terminal_queue.get()

            # Invalidate cache to force fresh content fetch (Fixes Stale Selection)
            manager.latest_page_content = None
            
            # Check content availability
            wait_count = 0
            while not manager.latest_page_content:
                if wait_count == 0:
                    print("🔄 Synchronizing with browser...") 
                    await manager.send_message("get_content", {})
                
                if wait_count % 5 == 0 and wait_count > 0:
                     print("⏳ Still waiting for page content... (Ensure a tab is open and refreshed)")
                     await manager.send_message("get_content", {})

                await asyncio.sleep(1.0)
                wait_count += 1
                
                # Optional: specific breakout command? 
                # For now, we block this specific question until content arrives.
            
            else:
                # Ask Agent
                print(f"🤖 Asking Agent: {question}")
                answer = await agent.ask(question, manager.latest_page_content)
                
                # --- PARSE HIGHLIGHTS ---
                # Extract text between ~tildes~
                highlights = re.findall(r'~(.+?)~', answer)
                for term in highlights:
                    print(f"✨ Highlighting: '{term}'")
                    await manager.send_message("highlight", {"text": term})
                    
                # Clean answer for display (replace ~text~ with **text**)
                clean_answer = re.sub(r'~(.+?)~', r'**\1**', answer)
                
                # Send to Browser
                success = await manager.send_message("ai_response", {
                    "question": question,
                    "answer": clean_answer
                })
                
                if success:
                    print(f"✅ Sent to Browser: {clean_answer[:50]}...")
                else:
                    print("❌ Failed to send to browser - no active connection")
                print("-" * 50)
                
        await asyncio.sleep(0.5)

# Terminal input handler (runs in thread)
def terminal_input_loop():
    print("\n" + "="*50)
    print("TERMINAL CHAT MODE")
    print("Type your question and press Enter.")
    print("="*50)
    
    while True:
        try:
            question = input("\n💬 Your question: ").strip()
            if question.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            if question:
                terminal_queue.put(question)
                print("⏳ Processing...")
        except:
            break

# Start terminal thread
worker_thread = threading.Thread(target=terminal_input_loop, daemon=True)
worker_thread.start()

# Pydantic model for REST API
class QuestionRequest(BaseModel):
    question: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting server...")
    asyncio.create_task(process_terminal_queue())
    yield
    # Shutdown
    print("👋 Shutting down server...")

# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API endpoint for run_cli.py
@app.post("/ask")
async def ask_question(request: QuestionRequest):
    """Handle questions from the CLI client"""
    print(f"📞 REST API Question: {request.question}")
    
    if not manager.latest_page_content:
        return {
            "status": "error",
            "response": "No page content available yet. Please wait for the extension to send page content."
        }
    
    try:
        # Ask the agent
        answer = await agent.ask(request.question, manager.latest_page_content)
        
        # Also send to browser via WebSocket if connected
        if manager.active_connection:
            await manager.send_message("ai_response", {
                "question": f"CLI: {request.question}",
                "answer": answer
            })
        
        return {
            "status": "success",
            "response": answer
        }
        
    except Exception as e:
        return {
            "status": "error",
            "response": f"Error processing question: {str(e)}"
        }

@app.websocket("/ws/client")
async def websocket_endpoint(websocket: WebSocket):
    # Accept WebSocket connections from any origin
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") in ["page_content", "page_content_push"]:
                manager.update_content(message.get("payload", ""))
            
            elif message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Health check endpoint
@app.get("/")
async def root():
    return {
        "status": "running",
        "websocket_connected": manager.active_connection is not None,
        "page_content_available": len(manager.latest_page_content) > 0 if manager.latest_page_content else False,
        "page_content_length": len(manager.latest_page_content) if manager.latest_page_content else 0
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting WebSocket server on ws://localhost:8000/ws/client")
    print("Starting REST API server on http://localhost:8000")
    print("Test with: curl -X POST http://localhost:8000/ask -H 'Content-Type: application/json' -d '{\"question\":\"Hello\"}'")
    uvicorn.run(app, host="0.0.0.0", port=8000)