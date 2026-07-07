# Walkthrough: Text-First Browser Guide

We have successfully built a robust, low-cost Browser Copilot that sees what you see (as text) and answers questions using OpenAI.

## 1. Architecture
*   **The Eyes (Chrome Extension)**: Injected into your active tab. It reads the page text intelligently. Features robust auto-injection and timeout recovery.
*   **The Nervous System (WebSocket)**: A persistent link between Chrome and the Python server.
*   **The Brain (Python Server)**: Receives page content and sends it to GPT-4o-mini.

## 2. Setup & Usage

### Step 1: Start the Brain
Open a terminal in `c:\AI PROJECT\PROJECT BOI` and run:
```powershell
# Ensure your venv is active
python browser_guide/backend/server.py
```
*You should see "Uvicorn running..."*

### Step 2: Wake up the Eyes
1.  Open Chrome.
2.  Make sure the **Browser Guide** extension is loaded.
3.  Navigate to any website (e.g., Wikipedia).
4.  **Check the icon**: The badge should change to "ON" (Green).

### Step 3: Chat!
Open a **new terminal** and run:
```powershell
python browser_guide/run_cli.py
```
Ask: *"What is this page about?"*

## 3. Resilience Features
We added several features to ensure it "just works":
*   **Auto-Injection**: If you forgot to refresh the page, the extension injects itself automatically.
*   **Smart Tab Finding**: It finds your active tab even if you are debugging in a separate DevTools window.
*   **Heartbeat**: Keeps the connection alive indefinitely.
*   **Timeouts**: If the page is stuck, the server resets and retries instead of hanging forever.

## 4. Next Steps
*   Integrate the Voice features (Kokoro) from your previous project.
*   Add "Commanding" capabilities (clicking buttons).
