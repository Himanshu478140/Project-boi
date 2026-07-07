# 🎙️ boi: Cognitive Proactive Voice Assistant

boi is a next-generation voice assistant built with a **Cognitive Loop** architecture. It goes beyond simple reactive commands, utilizing screen context and user activity history to model your cognitive state and intervene proactively when you get distracted or stuck.

---

## 🏗️ Architecture Overview

The system operates around a central **Orchestrator** and a decoupled **Event Bus**:

```
            +-------------------+
            |  Audio Input &    |
            |    VAD Engine     |
            +---------+---------+
                      | Speech Audio
                      v
            +---------+---------+
            |   Streaming STT   |
            +---------+---------+
                      | Text Transcript
                      v
            +---------+---------+
            |    Orchestrator   |<---+ Event Bus (Pub/Sub)
            +----+---------+----+
                 |         |
      Intent     |         | Observations (Window Title + Vision)
      Routing    v         v
+----------------+---+ +---+-----------------------------+
|    Router          | |       Cognitive Engine          |
|  - SOCIAL Mode     | |  - State Modeling (Coding, etc.)|
|  - PLANNER Mode    | |  - Distraction/Stuck Detection  |
|  - JARVIS Mode     | |  - Companionable Butler Conscience|
+--------------------+ +---------------------------------+
```

---

## ✨ Key Features

*   **🧠 Proactive Cognitive Loop**: Implements `Observation -> State Modeling -> Expectation -> Violation -> Intervention`. Detects user states like `Coding`, `Debugging`, `Entertainment`, `Meeting`, and `TheVoid`.
*   **🗣️ Natural Speech Synthesis**: Powered by [Kokoro ONNX](https://github.com/remsky/kokoro-onnx) supporting high-fidelity voice generation. Includes a model-warmup phase to ensure snappy responses during first-time inference.
*   **⚡ Intelligent Gating & Echo Protection**: Uses a smart 1.6-second "deaf window" after speaking to prevent acoustic feedback loops.
*   **📈 Semantic VAD**: Adjusts silence timeouts dynamically. Complete sentences trigger a fast timeout (~300ms) for snappy turn transitions, while incomplete sentences hold a patient timeout (~1000ms).
*   **🖥️ Local Vision & Browser Agency**: Parses active web content to suggest page interactions (clicking buttons/links, table extraction, form-filling, navigating) and visually grounds links.
*   **🔒 Built-in Security Engine**: Enforces role-based action validation before performing system tasks (e.g. running scripts or opening files).

---

## 📁 Repository Structure

*   [main.py](file:///c:/AI%20PROJECT/PROJECT%20BOI/main.py): Entrypoint to initialize and run the assistant loop.
*   [core/](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/): Main application package.
    *   [pipeline/](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/pipeline/): Core execution pipeline.
        *   [orchestrator.py](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/pipeline/orchestrator.py): Manages audio hardware, state machine transitions, event dispatch, and active threads.
        *   [event_bus.py](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/pipeline/event_bus.py): Pub-sub messaging system to decouple engines.
    *   [engines/](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/engines/): specialized sub-systems.
        *   [cognitive_engine.py](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/engines/cognitive_engine.py): Manages user state history, checks goal compliance, and runs the LLM-powered subconscious conscience.
        *   [tts_main.py](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/engines/tts_main.py): High-performance ONNX voice generation using GPU (FP32) or CPU (quantized Int8) targets.
        *   [profile_manager.py](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/engines/profile_manager.py): Tracks persistent user statistics, preferences, and identity facts.
        *   [browser_engine.py](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/engines/browser_engine.py): Automated Chrome-agent integration.
        *   [security_engine.py](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/engines/security_engine.py): Security layer validating script execution boundaries.
    *   [audio/](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/audio/): Low-level audio devices input/output.
    *   [config/](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/config/): Prompt structures and static configurations.

---

## 🚀 Getting Started

### 📋 Prerequisites

1.  **Python 3.10+**: Standard environment.
2.  **eSpeak NG**: Mandatory phonetic back-end for text-to-speech.
    *   On Windows, download and run the installer.
    *   Ensure the path matches [tts_main.py:12](file:///c:/AI%20PROJECT/PROJECT%20BOI/core/engines/tts_main.py#L12): `C:\Program Files\eSpeak NG\libespeak-ng.dll`.

### 🔧 Installation

1.  Set up the virtual environment:
    ```powershell
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    ```
2.  Place the Kokoro model and voice bin file in the root directory:
    *   `kokoro-v0_19.onnx` (Standard FP32 model for GPU)
    *   `kokoro-v1.0.int8.onnx` (Quantized Int8 model for CPU speed)
    *   `voices.bin` (Voice presets compiled library)

### 🏃 Running the Assistant

Execute the orchestrator:
```powershell
python main.py
```

Press `Ctrl+C` to terminate the voice assistant cleanly.

---

## 🛠️ Utility Command-Line Interface

*   **List Available Voices**:
    ```powershell
    python list_voices.py
    ```
*   **Migrate Legacy Profile Data**:
    ```powershell
    python migrate_profile.py
    ```

---

## 🧪 Developer Testing Commands

During active execution (when state is `LISTENING`), you can speak the following voice commands to trigger internal testing routines:

1.  **"test cognitive engine"**: Triggers an automated suite verifying state-tracking, transition rules, and butler prompt generation.
2.  **"test cognitive scenarios"**: Executes automated sequence scenarios demonstrating distraction triggers.
3.  **"set state <name>"**: Manually overrides the current state for sandbox testing (e.g. *"set state coding"*, *"set state entertainment"*).
