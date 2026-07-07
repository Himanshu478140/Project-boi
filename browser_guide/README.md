# How to Run Your Text-First Browser Guide

## 1. Load the Chrome Extension ("The Eyes")
1. Open Google Chrome.
2. Go to `chrome://extensions`.
3. Enable **Developer mode** (toggle in top right).
4. Click **Load unpacked** (top left).
5. Select this folder:
   `c:\AI PROJECT\PROJECT BOI\browser_guide\extension`
6. You should see the "Browser Guide (Text-First)" icon appear.
7. Pin it to your toolbar.

## 2. Start the "Brain" (Server)
1. Open a terminal in VS Code.
2. Run this command:
   ```bash
   python "c:\AI PROJECT\PROJECT BOI\browser_guide\backend\server.py"
   ```
3. You should see `Uvicorn running on http://0.0.0.0:8000`.

## 3. Connect & Chat
1. Open any website (e.g., Wikipedia) in Chrome.
2. Click the extension icon to verify it's active. (The badge should turn Green/say "ON").
3. Open a **second** terminal in VS Code.
4. Run the CLI:
   ```bash
   python "c:\AI PROJECT\PROJECT BOI\browser_guide\run_cli.py"
   ```
5. Type your question!
   *   "What is this page about?"
   *   "Summarize the main points."
