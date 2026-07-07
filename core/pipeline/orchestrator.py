import logging
import threading
import time
import queue
import numpy as np
import re
import asyncio
import os


# Components
from core.audio.input import AudioInput
from core.audio.output import AudioOutput
from core.engines.vad_engine import VADEngine
from core.engines.stt_engine import STTEngine
from core.utils.text_analyzer import TextAnalyzer
from core.engines.streaming_stt import StreamingSTT
from core.engines.router import Router, Route
from core.config.prompts import SYSTEM_PROMPT_SOCIAL, SYSTEM_PROMPT_PLANNER, SYSTEM_PROMPT_JARVIS
from core.engines.llm_engine import LLMEngine
from core.engines.tts_main import TTSMain
# from core.engines.tts_reflex import TTSReflex 
# from core.engines.paralinguistics import ParalinguisticEngine
from core.engines.memory import MemoryEngine
from core.engines.prosody import ProsodyEngine, SpeechChunk
from core.state.machine import StateMachine, State
from core.engines.interaction_reflex import InteractionReflexEngine
from core.engines.browser_engine import BrowserEngine
from core.engines.vision_engine import VisionEngine
from core.engines.system_engine import SystemEngine
from core.engines.profile_manager import ProfileManager
from core.engines.local_vision_engine import LocalVisionEngine
from core.engines.local_vision_engine import LocalVisionEngine
from core.engines.cognitive_engine import CognitiveEngine
from core.engines.cognitive_engine import CognitiveEngine
from core.engines.filesystem_engine import FileSystemEngine
from core.engines.text_engine import TextEngine
from core.engines.memory_integrator import MemoryIntegrator
from core.pipeline.event_bus import EventBus, EventType
from core.engines.security_engine import SecurityEngine, PermissionLevel

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        self.running = False
        self.test_mode = False
        
        # State
        self.state_machine = StateMachine()
        
        # Components
        self.audio_input = AudioInput()
        self.audio_output = AudioOutput()
        self.vad = VADEngine(threshold=0.5) # Tune threshold here
        self.stt = STTEngine()
        self.streaming_stt = StreamingSTT(self.stt, callback=self._on_stt_partial)
        self.llm = LLMEngine()
        self.tts = TTSMain()
        # self.reflex = TTSReflex(self.tts) 
        # self.paralinguistics = ParalinguisticEngine()
        self.tts = TTSMain()
        # self.reflex = TTSReflex(self.tts) 
        # self.paralinguistics = ParalinguisticEngine()
        self.memory = MemoryEngine(max_turns=10)
        self.interaction_reflex = InteractionReflexEngine()
        self.browser = BrowserEngine()
        self.vision = VisionEngine()
        self.system = SystemEngine()
        self.profile = ProfileManager()
        # self.local_vision = LocalVisionEngine(model="llava-phi3")
        self.local_vision = None # Fully disabled by user request
        self.cognitive = CognitiveEngine(llm_engine=self.llm)
        self.fs = FileSystemEngine()
        self.fs = FileSystemEngine()
        self.text_engine = TextEngine()
        self.memory_integrator = MemoryIntegrator(self.profile, self.llm)
        self.event_bus = EventBus()
        self.security = SecurityEngine()
        self.cognitive_enabled = False # User requested disable
        
        # --- Event Subscriptions ---
        # 1. Memory listens to RESPONSE_COMMITTED
        self.event_bus.subscribe(EventType.RESPONSE_COMMITTED, lambda data: self.memory_integrator.process_turn(data['user_text'], data['bot_text']))
        
        # 2. Proactivity listens to REFLECTION_PHASE
        self.event_bus.subscribe(EventType.REFLECTION_PHASE, lambda data: self._check_proactive_trigger(ignore_silence=True))

        
        # Proactive State
        self.last_proactive_check = 0
        self.PROACTIVE_INTERVAL = 10.0 # Check every 10s (User Request)
        
        # Buffers
        self.audio_buffer = [] # Accumulates float32 chunks for STT
        self.silence_chunks = 0
        self.speech_chunks = 0
        
        # Threads
        self.main_thread = None
        
        # Config
        self.DEFAULT_SILENCE_MS = 600
        self.FAST_SILENCE_MS = 300  # "Snappy" (Complete sentence)
        self.SLOW_SILENCE_MS = 1000 # "Patient" (Trailing connector)
        
        self.current_silence_threshold = self.DEFAULT_SILENCE_MS
        
        self.SPEECH_START_THRESHOLD_CHUNKS = 3 # ~100ms
        self.CHUNK_DURATION_MS = 32 # 512 / 16000

        self.last_real_turn_time = time.time()  # Time of last real conversation turn
        self.conversation_active = False  # Flag to track if we're in a real conversation
        self.PROACTIVE_COOLDOWN = 5.0
        
        # Smart Gating Config
        self.DEAF_WINDOW_MS = 1600 # 1.6s to cover 1.2s HW Latency
        self.last_speech_end_time = 0 
        
        # Dynamic Limit (calcuated on fly)
        # self.silence_chunk_limit = ... moved to property or dynamic check

    def _on_stt_partial(self, text, is_final):
        """Callback for Streaming STT visual feedback + Semantic VAD"""
        if not text:
            return
            
        if not is_final:
            # --- SEMANTIC VAD ANALYZER ---
            status, reason = TextAnalyzer.analyze(text)
            
            # Logic: Bias towards patience
            prev_threshold = self.current_silence_threshold
            
            if status == TextAnalyzer.COMPLETE:
                self.current_silence_threshold = self.FAST_SILENCE_MS
                indicator = "[!]"
            elif status == TextAnalyzer.INCOMPLETE:
                self.current_silence_threshold = self.SLOW_SILENCE_MS
                indicator = "[...]"
            else:
                self.current_silence_threshold = self.DEFAULT_SILENCE_MS
                indicator = "[ ]"
            
            # Visual Feedback in Console
            # Overwrite line for smooth UI effect
            # Format: "User (Partial): [!] Hello world...    "
            display_text = f"{indicator} {text}"
            print(f"\rUser (Partial): {display_text.ljust(70)}", end="", flush=True)
            pass
        else:
            # Final text will be logged by commit_turn
            pass

    def start(self):
        logger.info("Starting Orchestrator...")
        self.running = True
        
        # Start HW
        self.audio_input.start()
        self.audio_output.start()
        self.browser.start()
        
        
        # Start Main Loop
        self.main_thread = threading.Thread(target=self._loop, daemon=True)
        self.main_thread.start()
        
        # Contextual Greeting (Phase 2) - Disabled by user request
        # threading.Thread(target=self._initial_greeting, daemon=True).start()
        
        self.state_machine.set_state(State.LISTENING) # Start listening immediately

    def stop(self):
        self.running = False
        self.audio_input.stop()
        self.audio_output.shutdown()
        if self.main_thread:
            self.main_thread.join()

    def _loop(self):
        logger.info("Orchestrator Loop Started.")
        
        while self.running:
            # 1. Get Audio Chunk
            chunk = self.audio_input.get_chunk(timeout=0.1)
            if chunk is None:
                continue
                
            # --- SMART GATING (ECHO PROTECTION) ---
            # Gate if:
            # 1. Currently Speaking (Bot voice = Echo)
            # 2. Recently Spoke (Reverb = Echo) - 1.6s Window
            is_speaking_now = self.state_machine.current_state == State.SPEAKING
            time_since_speech = (time.time() - self.last_speech_end_time) * 1000
            
            if is_speaking_now or (time_since_speech < self.DEAF_WINDOW_MS):
                # Dropping input to prevent self-triggering
                continue
            # --------------------------------------
                
            # 2. VAD Check (Always run VAD)
            # Flatten if needed (input might be [512, 1])
            chunk_flat = chunk.flatten()
            is_speech = self.vad.is_speech(chunk_flat)

            if is_speech:
                self.interaction_reflex.on_user_activity()

            # --- ACTIVE LISTENING: PRESENCE CHECK ---
            if self.interaction_reflex.check_presence_prompt(self.state_machine.current_state == State.LISTENING):
                 logger.info("Triggering Presence Prompt: 'Are you there?'")
                 self._perform_reflex("Are you there?")
            # ----------------------------------------
            
            # DEBUG: VAD Visualization
            prob = self.vad.speech_probability
            input_energy = np.max(np.abs(chunk_flat))
            if prob > 0.1:
                # Simple visual bar
                bar = "#" * int(prob * 10)
                # Ensure we don't overwrite partial text too aggressively
                # print(f"\rVAD: [{bar:<10}] Prob: {prob:.2f} Energy: {input_energy:.2f}", end="", flush=True)
                pass

            # 3. Interruption Check
            if is_speech and self.state_machine.current_state == State.SPEAKING:
                logger.info("INTERRUPTION DETECTED!")
                self._handle_interruption()
                continue
                
            # --- PROACTIVE LOOP (Phase 2) ---
            # Run only if completely IDLE (Listening but silence)
            now = time.time()
            time_since_last_activity = now - self.interaction_reflex.last_user_activity

            if (self.state_machine.current_state == State.LISTENING and self.silence_chunks % 150 == 0 and self.silence_chunks > 0):
                 # HEARTBEAT LOG (every ~5s)
                 # logger.info(f"HEARTBEAT: Silent for {self.silence_chunks} chunks ({self.silence_chunks*0.032:.1f}s). "
                 #             f"ActiveLast: {time_since_last_activity:.1f}s ago. "
                 #             f"NextCheck: {self.PROACTIVE_INTERVAL - (now - self.last_proactive_check):.1f}s")
                 pass

            if (self.state_machine.current_state == State.LISTENING and
                time_since_last_activity > 5 and   # Only need 5s of user inactivity
                self.silence_chunks > 10 and # Not actively speaking
                (now - self.last_proactive_check > self.PROACTIVE_INTERVAL)):

                logger.info(f"Triggering proactive check (silence_chunks={self.silence_chunks}, time_since_last={now - self.last_proactive_check:.1f}s)")
                
                self.last_proactive_check = now
                threading.Thread(target=self._check_proactive_trigger, daemon=True).start()
            # --------------------------------
            
            # 4. State Handling
            current_state = self.state_machine.current_state
            
            if current_state == State.LISTENING:
                self._handle_listening(chunk_flat, is_speech)
            else:
                # STT Gating: Do not process audio in THINKING/SPEAKING states
                # This prevents "Words count mismatch" warnings and race conditions
                if self.speech_chunks > 0:
                     self.speech_chunks = 0
                     self.silence_chunks = 0
                pass

    def _handle_listening(self, chunk, is_speech):
        # Always feed streaming STT if we are tracking a turn
        
        if is_speech:
            self.speech_chunks += 1
            self.silence_chunks = 0
            self.audio_buffer.append(chunk)
            self.streaming_stt.process_chunk(chunk) # FEED STREAM
            if self.speech_chunks == 1:  # Only on first speech chunk
                self._update_conversation_timer()

        else:
            # Always track silence (even before speech starts) for Proactive Triggers
            self.silence_chunks += 1
            
            if self.speech_chunks > 0:
                # We were speaking, now silence
                # self.silence_chunks += 1 (Moved up)
                self.audio_buffer.append(chunk) # Keep slight trailing silence
                
                # FEED STREAM (Only if we assume potential completion, but silence is useful for context)
                self.streaming_stt.process_chunk(chunk) 

                # DYNAMIC SILENCE CHECK
                # 1. Get latest partial & stability
                partial_text = self.streaming_stt.get_current_text()
                is_stable = self.streaming_stt.is_stable()
                
                # 2. Analyze Completeness
                status, reason = TextAnalyzer.analyze(partial_text)
                
                # 3. Adjust Threshold logic
                # Default
                threshold = self.DEFAULT_SILENCE_MS
                
                if not is_stable:
                    # If STT is flickering (Hallucination risk), WAIT.
                    threshold = 1000 
                elif status == TextAnalyzer.FILLER:
                     # Pure Filler? IGNORE TIMEOUT.
                     self.silence_chunks = 0 # RESET SILENCE COUNT!
                     threshold = 3000
                elif status == TextAnalyzer.INCOMPLETE:
                     threshold = 1000 # Wait for more context

                     # --- ACTIVE LISTENING: PATIENCE ---
                     # (Removed by user request)
                     # ----------------------------------

                elif status == TextAnalyzer.COMPLETE:
                     threshold = 288 # Snappy
                
                self.current_silence_threshold = threshold
                chunk_limit = self.current_silence_threshold // self.CHUNK_DURATION_MS
                
                if self.silence_chunks > chunk_limit:
                    if status == TextAnalyzer.FILLER:
                        # Should not happen if we reset chunks, but safe fallback
                        pass
                    
                    if not is_stable:
                         logger.info(f"Force-Ending Unstable Turn (Timeout {threshold}ms): '{partial_text}'")
                    elif status == TextAnalyzer.INCOMPLETE:
                        logger.info(f"Force-Ending Incomplete Turn (Timeout {threshold}ms): '{partial_text}'")
                    
                    print() # Newline after partials
                    logger.info(f"Silence Timeout ({self.current_silence_threshold}ms) -> End of Turn")
                    
                    # FINAL STABILITY CHECK BEFORE COMMIT
                    self._commit_turn()
            else:
                # Just silence, buffering nothing
                pass

    def _commit_turn(self):
        self.state_machine.set_state(State.THINKING)

        self.conversation_active = True
        self.last_real_turn_time = time.time()
        logger.info(f"CONVERSATION: Turn started at {self.last_real_turn_time}")
        
        # Process Audio Buffer
        if not self.audio_buffer:
            logger.warning("Empty audio buffer committed.")
            self._reset_listening()
            return

        full_audio = np.concatenate(self.audio_buffer)
        self.audio_buffer = [] # Clear immediately
        self.speech_chunks = 0
        self.silence_chunks = 0
        
        # STT (Blocking for simple v1)
        audio_duration_sec = len(full_audio) / 16000 
        
        if audio_duration_sec < 0.5:
             logger.info(f"Audio too short ({audio_duration_sec:.2f}s). Ignoring.")
             self._reset_listening()
             return
 
        beam_size = 5 if audio_duration_sec < 3.0 else 1
        
        start_stt = time.time()
        # logger.info(f"STT Processing: {audio_duration_sec:.2f}s audio | Beam Size: {beam_size}")
        
        # Using StreamingSTT commit for final result
        text = self.streaming_stt.commit() 
        t1 = time.time() 
        logger.info(f"TIMING: T0->T1 (STT Finalize): {(t1 - start_stt)*1000:.0f}ms")
        
        # Normalization (Basic Clean-up)
        text_clean = text.strip().replace("\n", " ").replace("  ", " ")
        # Regex to remove starting fillers: "Um, ", "Uh, ", "Right, "
        text_clean = re.sub(r'^(um|uh|so|right|like)[,.]?\s*', '', text_clean, flags=re.IGNORECASE)
        
        if text_clean.lower().startswith("want to"):
            text_clean = "Do you " + text_clean
        if text_clean.lower().startswith("maybe") and "to" in text_clean:
            # "Maybe to the bar" -> "Maybe we could go to..." is risky.
            # Let's just fix the grammar slightly if obvious.
            pass 
            
        # Light Polish (Heuristic fixes for known STT quirks)
        # "sooth dreams" -> "sweet dreams" (Example from logs)
        text_clean = text_clean.replace("sooth dreams", "sweet dreams")
        text_clean = text_clean.replace("go a walk", "go for a walk")
        
        # Fix common STT artifacts if simple
        text_clean = text_clean[0].upper() + text_clean[1:] if text_clean else ""
        words = text_clean.split()

        # --- ADD THE TEST TRIGGER HERE ---
        if text_clean.lower().strip(" .!") == "test cognitive engine":
            logger.info("=== MANUAL COGNITIVE ENGINE TEST ===")
            self.test_mode = True
            # Note: Ensure the method name matches your definition (test_cognitive_engine)
            self._test_cognitive_engine() 
            self._reset_listening() # Return to listening state after test
            return

        if text_clean.lower().strip(" .!") == "test cognitive scenarios":
            logger.info("=== TESTING COGNITIVE SCENARIOS ===")
            self.test_mode = True
            self._test_cognitive_scenarios()
            self._reset_listening()
            return

        # In orchestrator.py _commit_turn method:
        if text_clean.lower().strip(" .!").startswith("set state "):
            state_name = text_clean[10:].strip().capitalize()  # "set state coding" -> "Coding"
            valid_states = ["Coding", "Debugging", "Reading", "Entertainment", "Meeting", "Thevoid"]
            
            if state_name.lower() in [s.lower() for s in valid_states]:
                # Convert "Thevoid" to "TheVoid"
                if state_name.lower() == "thevoid":
                    state_name = "TheVoid"
            
                logger.info(f"Manually setting cognitive state to: {state_name}")
                self.cognitive.set_state_for_testing(state_name)
                self._synthesize_and_play(f"State set to {state_name}.", pause_duration=0)
                self._reset_listening()
                return
        # ----------------------------------
        
        # Gate 2: Fragment Suppression
        if not text_clean or len(words) < 2:
            logger.info(f"Fragment Ignored (Too short): '{text_clean}'")
            self._reset_listening()
            return
            
        blocklist = ["Thank you.", "You're welcome.", "Thanks for watching.", "You"]
        if text_clean in blocklist:
            logger.info(f"Fragment Ignored (Blocklist): '{text_clean}'")
            self._reset_listening()
            return
            
        logger.info(f"User Said: {text_clean}")
        
        # Notify Reflex Engine (Turn Completed)
        self.interaction_reflex.on_turn_commit()
        
        # --- INTERRUPTION OVERRIDE ---
        # Explicit commands to stop speech immediately without LLM turn.
        # "Stop", "Wait", "Cancel", "Shut up", "Silence"
        stop_triggers = ["stop", "wait", "pause"]
        clean_lower = text_clean.lower().strip(" .!")
        
        if clean_lower in stop_triggers:
            logger.info(f"Interruption Triggered: '{text_clean}'")
            
            # Synthesize acknowledgement directly (Talker speed)
            self.state_machine.set_state(State.SPEAKING) 
            
            # Use pre-generated 'acknowledgement' fillers for ZERO LATENCY
            # (No TTS generation needed here)
            sequence = self.paralinguistics.get_sequence(intent="acknowledgement")
            
            for event in sequence:
                if event.type == "filler": # We only want the vocal ack, not an inhale here
                    self.audio_output.play_chunk(event.audio, volume_gain=event.gain)
            
            # Wait for ack to complete (optional, or just drift into listening)
            while self.audio_output.is_playing():
                time.sleep(0.05)
                
            self._reset_listening()
            return
        # -----------------------------
        
        # --- ROUTING ---
        # --- ROUTING ---
        route = Router.route(text_clean)
        
        # --- ROUTING OVERRIDE (Browser Agency) ---
        # Router often thinks "Click the button" is Social. We force Jarvis if keywords exist.
        if any(w in text_clean.lower() for w in ["click", "press", "select", "type", "enter", "scroll", "go to", "open", "back", "reload", "refresh", "fill", "form", "table", "visit", "navigate"]) or ("." in text_clean and len(text_clean.split()) < 5):
            if route != Route.JARVIS:
                logger.info(f"Routing Override: Forced JARVIS for Browser Command (was {route})")
                route = Route.JARVIS
        # ----------------------------------------

        # --- ACTIVE LISTENING: UNCERTAINTY MIRRORING ---
        # (Removed by user request)
        # -----------------------------------------------

        # ---------------

        # --- REALISM (BREATHING/THINKING) ---
        # Disabled (Phase 19 Refactor)
        # para_intent = "thinking" if route == Route.PLANNER else "reflex"
        # ------------------------------------

        # LLM + TTS Flow
        self._generate_response(text_clean, route)

    def _generate_response(self, text, route):
        # Run generation in a separate thread so _loop can continue VAD checks
        threading.Thread(target=self._generate_response_worker, args=(text, route), daemon=True).start()

    def _generate_response_worker(self, text, route):
        self.state_machine.set_state(State.SPEAKING)
        
        # 1. Behavior Prompt
        if route == Route.PLANNER:
            behavior_prompt = SYSTEM_PROMPT_PLANNER
            logger.info("Exec Mode: PLANNER (Deep Reasoning)")
        elif route == Route.JARVIS:
            behavior_prompt = SYSTEM_PROMPT_JARVIS
            logger.info("Exec Mode: JARVIS (System/Vision)")
        else: # SOCIAL / Default
            behavior_prompt = SYSTEM_PROMPT_SOCIAL
            logger.info("Exec Mode: SOCIAL (Conversational)")

        # 2. Static User Context
        user_context_str = self.profile.get_context_string()

        # 3. Assemble Messages list
        # We explicitly separate behavior and context
        messages = [
            {"role": "system", "content": behavior_prompt},
            {"role": "system", "name": "user_context", "content": user_context_str}
        ]
        
        # Inject Short-Term Memory
        messages.extend(self.memory.get_history())
        
        # Add Current Turn
        # Handle Vision Input (See/Look/Read)
        if self.local_vision and route == Route.JARVIS and any(w in text.lower() for w in ["see", "screen", "look", "read", "what is"]):
            logger.info("Vision Request -> Local LLM (llava-phi3)")
            vision_response = self.local_vision.analyze_screen(prompt=text)
            if vision_response:
                 logger.info(f"Local Vision Output: {vision_response}")
                 context_msg = f"[SYSTEM VISION RESULT]: User asked '{text}'. Local Vision Analysis: '{vision_response}'"
                 messages.append({"role": "system", "content": context_msg})
                 messages.append({"role": "user", "content": text}) 
            else:
                 logger.warning("Local Vision Failed.")
                 messages.append({"role": "user", "content": text + " [System Note: Vision failed.]"})

        # Handle File Search Input (Search/Find File)
        elif route == Route.JARVIS and any(w in text.lower() for w in ["search for", "find file", "where is", "locate"]):
            logger.info("FileSystem Request -> FileSystemEngine")
            # Extract query: remove "search for", "find file"
            query = text.lower().replace("search for", "").replace("find file", "").replace("where is", "").replace("locate", "").strip()
            
            results = self.fs.search(query=query)
            if results:
                file_list = "\n".join(results[:5]) # Top 5
                context_msg = f"[SYSTEM FILE SEARCH]: Found matches for '{query}':\n{file_list}\n(Tell user you found these. Ask if they want to open one.)"
                messages.append({"role": "system", "content": context_msg})
                messages.append({"role": "user", "content": text})
            else:
                messages.append({"role": "system", "content": f"[SYSTEM FILE SEARCH]: No files found matching '{query}'."})
                messages.append({"role": "user", "content": text})

        # Handle Open File (Open/Launch)
        elif route == Route.JARVIS and any(w in text.lower() for w in ["open", "launch", "run"]):
             logger.info("FileSystem Request -> Open File")
             target = text.lower().replace("open", "").replace("launch", "").replace("run", "").strip()
             
             # 1. Try exact path (if extracted previously)
             if "." in target and (os.path.exists(target) or "\\" in target):
                 # Security Check
                 perm = self.security.validate("open", target)
                 if perm == PermissionLevel.AUTO:
                     if self.fs.open_file(target):
                         messages.append({"role": "system", "content": f"[SYSTEM]: Successfully opened '{target}'."})
                     else:
                         messages.append({"role": "system", "content": f"[SYSTEM]: Failed to open '{target}'."})
                 else:
                     messages.append({"role": "system", "content": f"[SYSTEM SECURITY]: Opening '{target}' blocked (Risk Level: {perm.name}). Inform user."})
             else:
                 # 2. Search and open first match
                 results = self.fs.search(target, limit=1)
                 if results:
                     path = results[0]
                     # Security Check
                     perm = self.security.validate("open", path)
                     if perm == PermissionLevel.AUTO:
                         if self.fs.open_file(path):
                             messages.append({"role": "system", "content": f"[SYSTEM]: Found and opened '{path}'."})
                         else:
                             messages.append({"role": "system", "content": f"[SYSTEM]: Found '{path}' but failed to open it."})
                     else:
                         messages.append({"role": "system", "content": f"[SYSTEM SECURITY]: Found '{path}' but opening was blocked (Risk Level: {perm.name}). Inform user."})
                 else:
                     messages.append({"role": "system", "content": f"[SYSTEM]: Could not find file matching '{target}' to open."})
             
             messages.append({"role": "user", "content": text})
        
        # Handle Browser Actions (Click/Type/Scroll)
        elif route == Route.JARVIS and any(w in text.lower() for w in ["click", "press", "select", "type", "enter", "scroll", "go to", "open", "back", "reload", "refresh", "fill", "form", "table"]):
            logger.info("Browser Control Request")
            loop = self.browser.loop
            
            if not loop:
                messages.append({"role": "system", "content": "[SYSTEM ERROR]: Browser not connected. Cannot perform action."})
                logger.error("Browser Loop not available (Extension not connected?)")
                # Continue flow to at least respond to user
            
            else:
                # Simple Keyword Matching (Refine with LLM later if needed)
                lower_text = text.lower()
                
                # cleaner for conversational fillers
                for filler in ["can you", "could you", "would you", "please", "just", "hey jarvis", "jarvis"]:
                    lower_text = lower_text.replace(filler, "")
                
                lower_text = lower_text.strip()
                
                if "scroll" in lower_text:
                    direction = "up" if "up" in lower_text else "down"
                    asyncio.run_coroutine_threadsafe(self.browser.scroll(direction), loop)
                    messages.append({"role": "system", "content": f"[SYSTEM]: Scrolled {direction}."})
                    
                elif "click" in lower_text or "press" in lower_text or "select" in lower_text:
                    # Positional Parsing: Get everything AFTER the verb
                    target = ""
                    for verb in ["click", "press", "select"]:
                        if verb in lower_text:
                            # Split by verb, take the last part (suffix)
                            # e.g. "can you click on the login button" -> ["can you ", " on the login button"]
                            parts = lower_text.split(verb, 1)
                            if len(parts) > 1:
                                target = parts[1].strip()
                                break
                    
                    # Cleanup leading prepositions
                    # Cleanup leading prepositions
                    for prefix in ["on ", "the ", "at ", "to "]:
                        if target.startswith(prefix):
                            target = target[len(prefix):].strip()
                    
                    # Cleanup suffixes (User often says "Click X button")
                    for suffix in [" button", " link", " icon", " tab", " menu"]:
                         if target.endswith(suffix):
                             target = target[:-len(suffix)].strip()
                    
                    # Cleanup punctuation
                    target = target.rstrip("?!.:;")
                            
                    asyncio.run_coroutine_threadsafe(self.browser.click(target), loop)
                    messages.append({"role": "system", "content": f"[SYSTEM]: Clicked '{target}'."})

                elif "table" in lower_text:
                    # Generic table extraction (grabs largest table)
                    asyncio.run_coroutine_threadsafe(self.browser.extract_table(), loop)
                    messages.append({"role": "system", "content": f"[SYSTEM]: Requesting table data..."})

                # --- NEW NAVIGATION & FORM FILLING ---
                elif any(w in lower_text for w in ["go to", "open", "navigate to", "visit"]) or (("http" in lower_text or "www" in lower_text or ".com" in lower_text or ".org" in lower_text) and len(lower_text.split()) < 5):
                    # Extract URL
                    url = ""
                    words = text.split()
                    for w in words:
                        if "." in w and ("http" in w or "www" in w or ".com" in w or ".org" in w or ".net" in w or ".io" in w):
                            url = w.strip(".,;?!")
                            if not url.startswith("http"): url = "https://" + url
                            break
                    
                    # Fallback: if user just said "open Wikipedia", map to wikipedia.org
                    if not url and "wikipedia" in lower_text: url = "https://wikipedia.org"
                    if not url and "google" in lower_text: url = "https://google.com"
                    if not url and "youtube" in lower_text: url = "https://youtube.com"
                    if not url and "twitter" in lower_text: url = "https://twitter.com"
                    if not url and "x.com" in lower_text: url = "https://x.com"

                    if url:
                         asyncio.run_coroutine_threadsafe(self.browser.navigate(url), loop)
                         messages.append({"role": "system", "content": f"[SYSTEM]: Navigating to {url}..."})
                    else:
                         messages.append({"role": "system", "content": f"[SYSTEM]: Could not extract URL from '{text}'. Ask user for full domain."})

                elif "back" in lower_text and "go" in lower_text:
                    asyncio.run_coroutine_threadsafe(self.browser.back(), loop)
                    messages.append({"role": "system", "content": "[SYSTEM]: Navigating Back."})

                elif "reload" in lower_text or "refresh" in lower_text:
                    asyncio.run_coroutine_threadsafe(self.browser.reload(), loop)
                    messages.append({"role": "system", "content": "[SYSTEM]: Reloading page."})
                    
                elif "fill" in lower_text and "form" in lower_text:
                    # Smart Form Filling (Uses Profile)
                    # For now, we mock the profile data or use a simple subset
                    # user_profile = self.profile.get_flattened_data() # Assuming this exists
                    user_profile = {
                        "name": "Himanshu",
                        "first_name": "Himanshu",
                        "last_name": "Singh",
                        "email": "himanshu@example.com",
                        "phone": "555-0123",
                        "address": "123 AI Blvd",
                        "city": "San Francisco",
                        "zip": "94105"
                    }
                    asyncio.run_coroutine_threadsafe(self.browser.fill_form(user_profile), loop)
                    messages.append({"role": "system", "content": "[SYSTEM]: Auto-filling form with profile data."})
                    
                elif "type" in lower_text or "enter" in lower_text:
                    # Logic for "Type X into Y" or just "Type X" (focused)
                     # Positional Parsing for Type
                    content = ""
                    target = ""
                    
                    action_verb = "type" if "type" in lower_text else "enter"
                    
                    if "into" in lower_text:
                        # "Type hello world into the search box"
                        # Split by 'type' then 'into'
                        suffix = lower_text.split(action_verb, 1)[1] # " hello world into the search box"
                        parts = suffix.split("into", 1)
                        content = parts[0].strip()
                        target = parts[1].strip()
                    else:
                        # "Type hello world" (Implicit target)
                        content = lower_text.split(action_verb, 1)[1].strip()
                        target = "__focused__" # Browser engine should handle this or fail gracefully
                        
                    # Cleanup target prepositions
                    for prefix in ["the ", "in ", "on "]:
                         if target.startswith(prefix):
                             target = target[len(prefix):].strip()

                    asyncio.run_coroutine_threadsafe(self.browser.type_text(target, content), loop)
                    messages.append({"role": "system", "content": f"[SYSTEM]: Typed '{content}' into '{target}'."})

            # Critical: Instruct LLM to be concise for actions
            messages.append({"role": "system", "content": "[SYSTEM]: Browser Action Executed. DO NOT explain the page content. Just confirm with 'Done' or 'Scrolled'."})
            messages.append({"role": "user", "content": text})

        else:
            # Standard Text Input
            messages.append({"role": "user", "content": text})

        # --- BROWSER CONTEXT INJECTION ---
        page_content = self.browser.get_content()
        if page_content:
            logger.info("Injecting Browser Context...")
            # System instruction for visual grounding
            messages.append({
                "role": "system", 
                "content": "VISUAL GROUNDING: Enclose specific buttons/links/text in ~tildes~ to highlight them in the user's browser (e.g., Click ~Sign Up~)."
            })
            # The actual content
            messages.append({
                "role": "assistant",
                "name": "browser_context",
                "content": f"USER'S BROWSER CONTEXT:\n{page_content}"
            })
        # ---------------------------------

        # --- SYSTEM CONTEXT INJECTION ---
        system_context = self.system.get_context()
        if system_context:
             messages.append({
                "role": "system",
                "name": "os_context",
                "content": system_context
             })
        # --------------------------------

        buffer = ""
        full_response = "" # Accumulator for Memory
        first_token_received = False
        t_start_gen = time.time()
        
        # --- TEXT-BASED REFLEX STRATEGY ---
        # (Disabled/Removed by User Request)
        # ---------------------------
        
        try:
            # Pass full messages list to LLM
            model_to_use = "gpt-4o-mini"
            # Route.VISION is now handled upstream via context injection, so we use Mini for specific speech generation
            if route == Route.PLANNER:
                model_to_use = "gpt-4o" # Keep 4o for Planning/Reasoning if needed
            
            for token in self.llm.generate_stream(messages, model=model_to_use):
                if not first_token_received:
                    t2 = time.time() # T2: First Token
                    logger.info(f"TIMING: T1->T2 (LLM Network): {(t2 - t_start_gen)*1000:.0f}ms")
                    first_token_received = True

                # Check interruption
                if self.state_machine.current_state != State.SPEAKING:
                    logger.info("LLM Generation halted (Interruption).")
                    return

                buffer += token
                full_response += token
                
                # --- HIGHLIGHT PARSING ---
                # Simple check for ~highlight~ patterns
                if "~" in token:
                     # Check if we have a closed highlight in the full response buffer
                     highlights = re.findall(r'~(.+?)~', full_response)
                     for term in highlights:
                         # Use a simple "seen" set or just simplistic dedupe if needed
                         # For now, just fire. Browser handles redundacy gracefully?
                         # Better: Check if this *specific* match is new. 
                         # Simple approach: Fire all found. Browser side is lightweight.
                         # Optimization: loop only over *new* matches? 
                         # Let's trust the browser engine to handle rapid fires or just let it pulse.
                         if self.browser.loop:
                             asyncio.run_coroutine_threadsafe(self.browser.highlight(term), self.browser.loop)
                # -------------------------

                # --- BRANCHING OUTPUT LOGIC ---
                # --- BRANCHING OUTPUT LOGIC ---
                if route == Route.SOCIAL:
                    # SOCIAL: Aggressive Pipelining
                    # Trigger on punctuation to keep flow moving fast
                    if len(buffer) > 15: 
                        chunk_text = None
                        for punct in [". ", "? ", "! ", ".\n", ", ", " and ", " but "]:
                            if punct in buffer:
                                parts = buffer.split(punct, 1)
                                separator = punct
                                chunk_text = parts[0] + separator.strip()
                                buffer = parts[1]
                                break
                        
                        if chunk_text:
                            # Prosody Pass
                            logger.info(f"JARVIS: {chunk_text}")
                            chunks = ProsodyEngine.process(chunk_text, intent="casual")
                            for chunk in chunks:
                                self._process_speech_chunk(chunk)
                                
                elif route == Route.PLANNER:
                    # PLANNER: Conservative Pipelining
                    if len(buffer) > 20: # Wait for more context
                        chunk_text = None
                        for punct in [". ", "? ", "! ", ".\n", ":\n"]: # Support lists/colons
                            if punct in buffer:
                                parts = buffer.split(punct, 1)
                                separator = punct
                                chunk_text = parts[0] + separator.strip()
                                buffer = parts[1]
                                break
                        
                        if chunk_text:
                            # Prosody Pass
                            logger.info(f"JARVIS: {chunk_text}")
                            chunks = ProsodyEngine.process(chunk_text, intent="explanation")
                            for chunk in chunks:
                                self._process_speech_chunk(chunk)
        
        except Exception as e:
            logger.error(f"Generation Error: {e}")
            self.state_machine.set_state(State.LISTENING)
            return
            
        # Process remaining buffer
        if buffer.strip():
            # Final flush
            logger.info(f"JARVIS: {buffer}")
            intent = "casual" if route == Route.SOCIAL else "explanation"
            chunks = ProsodyEngine.process(buffer, intent=intent)
            for chunk in chunks:
                self._process_speech_chunk(chunk)
            
        # --- MEMORY COMMIT ---
        # If we reached here without exception/interruption, commit to memory.
        
        # 1. Long-Term Memory (Profile Update)
        # A. Explicit "Remember that" (Legacy/Direct)
        lower_text = text.lower()
        if "remember that" in lower_text or "remember i" in lower_text:
             # ... (Keep existing logic) ...
             if "remember that" in lower_text:
                 fact = text.split("remember that", 1)[1].strip()
                 # ...
                 self.profile.remember_fact(fact)
                 logger.info(f"Explicit Memory Updated: '{fact}'")

        # B. Implicit Auto-Memory (Background Extraction)
        # Run in thread to not block TTS
        threading.Thread(target=self._auto_memory_worker, args=(text,), daemon=True).start()

        # 2. Short-Term Memory
        # Check one last time if we are still speaking (not interrupted during last chunk match)
        interrupted = self.state_machine.current_state != State.SPEAKING
        
        if not interrupted and full_response:
             self.memory.add("user", text)
             self.memory.add("assistant", full_response)
             logger.info("Turn committed to Memory.")
        # ---------------------
            
        # Wait for all audio to finish playing
        while self.audio_output.is_playing() and self.state_machine.current_state == State.SPEAKING:
            time.sleep(0.1)
            
        # Natural finish
        if self.state_machine.current_state == State.SPEAKING:
            logger.info("Playback finished naturally.")
            
            # --- GATING START ---
            self.last_speech_end_time = time.time()
            self.audio_input.clear() # Flush echo that happened DURING speech
            logger.info(f"Gating Input for {self.DEAF_WINDOW_MS}ms (Echo Protection)")
            # --------------------
            
            self._reset_listening()

            # --- EVENT DRIVEN ARCHITECTURE ---
            # 1. Commit Memory
            self.event_bus.publish(EventType.RESPONSE_COMMITTED, {'user_text': text, 'bot_text': full_response})
            
            # 2. Trigger Reflection (Proactivity)
            logger.info("Triggering REFLECTION_PHASE Event...")
            self.event_bus.publish(EventType.REFLECTION_PHASE)
            # ---------------------------------

    def _process_speech_chunk(self, chunk):
        """Helper to synthesize and play a prosody chunk"""
        if not chunk.text.strip():
            return
            
        # Check if we need to interrupt the filler (Thinking sound)
        if self.state_machine.current_state == State.THINKING:
            # We are transitioning from THINKING (Filler playing) to SPEAKING (Real response)
            # Cut off the filler for snappiness.
            self.audio_output.stop_immediate()
            time.sleep(0.02) # yield to allow queue drain
            self.state_machine.set_state(State.SPEAKING)
            
        # 1. Synthesize (Speed)
        audio_chunks, sr = self.tts.synthesize(chunk.text, speed=chunk.speed)
        
        if audio_chunks is not None:
             # 2. Play (Volume)
             self.audio_output.play_chunk(audio_chunks, volume_gain=chunk.volume_gain)
             
             # 3. Pause
             if chunk.pause_after_ms > 0:
                 pause_samples = int(24000 * (chunk.pause_after_ms / 1000.0))
                 pause_chunk = np.zeros(pause_samples, dtype=np.float32)
                 self.audio_output.play_chunk(pause_chunk, volume_gain=0.0)

    # Legacy method kept/redirected if needed, but primarily replaced by _process_speech_chunk
    def _synthesize_and_play(self, text, pause_duration=0.2):
         # Wrapper for legacy calls (like interruptions)
         # Assume "neutral" intent
         chunks = ProsodyEngine.process(text, intent="neutral")
         for chunk in chunks:
             # Override pause if manually specified? 
             # For legacy simple calls, just use the engine's default.
             self._process_speech_chunk(chunk)
             
         # Manual pause padding if requested (legacy arg)
         if pause_duration > 0:
             pause_samples = int(24000 * pause_duration)
             pause_chunk = np.zeros(pause_samples, dtype=np.float32)
             self.audio_output.play_chunk(pause_chunk)

    def _handle_interruption(self):
        logger.info("Handling Interruption...")
        # 1. Kill Output
        self.audio_output.stop_immediate()
        
        # 2. Reset State (This signals _generate_response_worker to stop)
        self._reset_listening()


    def _reset_listening(self):
        self.audio_buffer = []
        self.speech_chunks = 0
        self.silence_chunks = 0
        self.streaming_stt.reset() # CRITICAL: Clear streaming buffer
        self.state_machine.set_state(State.LISTENING)

    def _perform_reflex(self, text):
        """
        Executes an Active Listening reflex (Safe Mode).
        1. Switches to SPEAKING (Gates input).
        2. Plays Audio (Blocking).
        3. Clears Buffer (Removes Echo).
        4. Restores previous state.
        """
        logger.info(f"Performing Reflex: '{text}'")
        
        previous_state = self.state_machine.current_state
        self.state_machine.set_state(State.SPEAKING)
        
        # 1. Play
        self._synthesize_and_play(text, pause_duration=0)
        
        # 2. Block until done (Prevent loop from processing echo)
        while self.audio_output.is_playing():
            time.sleep(0.05)
            
        # 3. Cleanup Echo
        self.last_speech_end_time = time.time()
        self.audio_input.clear() # CRITICAL: Flush the echo that queued up
        logger.info(f"Reflex Complete. Cleared Buffer. restoring {previous_state.name}")
        
        # 4. Restore
        # If the state was THINKING, we return to THINKING.
        # If LISTENING, return to LISTENING.
        
        # SPECIAL CASE: if we were LISTENING, we should probably reset STT too?
        # Actually, audio_input.clear() helps, but streaming_stt might have partials of the echo?
        # If we blocked well, STT shouldn't have seen it.
        # But just in case:
        if previous_state == State.LISTENING:
            self.streaming_stt.reset()
            
        self.state_machine.set_state(previous_state)

    # _get_contextual_filler deleted by user request

    # In the _check_proactive_trigger method:
    def _check_proactive_trigger(self, ignore_silence=False):
        """
        Called periodically (or by event) to see if we should interrupt/speak.
        """
        if not self.cognitive_enabled:
             return
             
        now = time.time()
        try:
            logger.info("=== PROACTIVE CHECK ENTERED ===")
            logger.info(f"  - Current State: {self.state_machine.current_state.name}")
            logger.info(f"  - ignore_silence flag: {ignore_silence}")
            # 0. Double-check we're still in listening state
            if self.state_machine.current_state != State.LISTENING:
                logger.info("Proactive check skipped - not in LISTENING state")
                return
            
            # 1. Check if user has been silent for a while
            current_time = time.time()
            time_since_last_activity = current_time - self.interaction_reflex.last_user_activity

            logger.info(f"  - Time since user activity: {time_since_last_activity:.1f}s")
        
            # Only run proactive check if user has been silent for > 5 seconds (Unless forced)
            MIN_INACTIVITY = 5.0
            if not ignore_silence and time_since_last_activity < MIN_INACTIVITY:
                logger.info(f"  - Skipped: User active {time_since_last_activity:.1f}s ago (need {MIN_INACTIVITY}s)")
                return
        
            logger.info(f"  - User inactive for: {time_since_last_activity:.1f}s")
        
            # 2. Quick System Check
            app_name = self.system.get_active_app_name()
        
            if not app_name: 
                logger.info("  - No active app, skipping")
                return

            logger.info(f"  - Active app: {app_name}")

            # 3. Text Extraction (UIA) - Replaces Proactive Vision
            # User Preference: "keep vision for screenshot... and for rest use uiautomation"
            logger.info("  - Extracting focused text...")
            # We treat the extracted text as the "description" for the cognitive engine
            # Truncate to 4000 chars (was 500)
            desc = self.text_engine.get_focused_text(max_chars=4000)
            
            if not desc:
                # Fallback? Or just say "User is clicking around"
                # If text extraction fails, we might just assume interaction without content
                desc = "User is interacting with the UI (No text content)"
                logger.info("  - No text extracted.")
            else:
                 logger.info(f"  - Text Content (First 50): '{desc[:50]}...'")
            
            # 4. Cognitive Engine Update
            logger.info("  - Updating cognitive engine...")
            needs_intervention, message = self.cognitive.update_observation(app_name, desc)
        
            logger.info(f"  - Cognitive result: needs={needs_intervention}, message='{message}'")
        
            if needs_intervention and message:
                logger.info(f"=== PROACTIVE INTERVENTION TRIGGERED: {message} ===")
            
                # Double-check we're still in listening state
                if self.state_machine.current_state != State.LISTENING:
                    logger.info("  - Skipped: no longer in LISTENING state")
                    return
            
                # Check cooldown - don't interrupt too soon after last speech
                self.last_real_turn_time = time.time()
                proactive_msg = f"[SYSTEM INTERVENTION]: {message}"
                self._commit_turn_proactive(proactive_msg)
            else:
                logger.info("  - No intervention needed")
            
        except Exception as e:
            logger.error(f"Proactive check failed: {e}", exc_info=True)
        finally:
            logger.info("=== PROACTIVE CHECK COMPLETE ===")

    def _update_conversation_timer(self):
        """Reset conversation timer when user speaks"""
        self.last_real_turn_time = time.time()
        logger.info(f"CONVERSATION: Timer reset at {self.last_real_turn_time}")

    def _commit_turn_proactive(self, system_msg):
        """
        Injects a system-initiated turn.
        """
        self.state_machine.set_state(State.THINKING)
        logger.info(f"Initiating Proactive Turn: {system_msg}")
        
        # Synthesize a soft "Ding" or "Throat clear"
        # self._play_notification() # Todo
        
        # Generate Response
        # Generate Response
        # Route as SOCIAL (Conversational) to avoid triggering Vision Engine (Screen Analysis)
        # We already gathered context via TextEngine/CognitiveEngine.
        self._generate_response(system_msg, Route.SOCIAL)


    def _auto_memory_worker(self, text):
        """
        Background thread to extract facts OR active tasks from user text.
        """
        try:
            if len(text.split()) < 4:
                return

            # Shared extraction step
            prompt = (
                "Analyze user text. \n"
                "1. If they state a GOAL/TASK (e.g. 'I am debugging login'), return 'GOAL: <goal>'.\n"
                "2. If they state a FACT (e.g. 'My API key is 123'), return 'FACT: <fact>'.\n"
                "3. Otherwise return 'None'."
            )

            response = self.llm.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=60
            )
            result = response.choices[0].message.content.strip()
            
            if result.startswith("FACT:"):
                fact = result.replace("FACT:", "").strip()
                if self.profile.remember_fact(fact):
                     logger.info(f"Auto-Memory Saved: '{fact}'")
                     
            elif result.startswith("GOAL:"):
                goal = result.replace("GOAL:", "").strip()
                self.cognitive.set_active_task(goal)
                
        except Exception as e:
            logger.error(f"Auto-Memory Error: {e}")

    # Add a test method to orchestrator.py
    def _test_cognitive_engine(self):
        """
        Manually triggers a check of the Cognitive Engine state.
        Useful for debugging via voice command 'test cognitive engine'.
        """
        logger.info("--- Manual Cognitive Engine Diagnosis ---")
        
        # Build System Prompt
        base_prompt = SYSTEM_PROMPT_SOCIAL
        
        # Inject Profile (Project Elephant)
        profile_context = self.profile.get_context_string()
        if profile_context:
            base_prompt += f"\n{profile_context}\n"
        
        # Inject Cognitive Context (State)
        cog_state = self.cognitive.current_state.name
        cog_desc = self.cognitive.current_description[:2000] # Provide current screen text to Main LLM too
        context_prompt = f"\n[System Context]:\nUser State: {cog_state}\nScreen Content: {cog_desc}\n"
        
        full_prompt = base_prompt + context_prompt
        
        # 1. Check Current State
        current_state = self.cognitive.current_state
        logger.info(f"Current Cognitive State: {current_state}")
        
        # 2. Check History
        history_len = len(self.cognitive.state_history)
        logger.info(f"State History Depth: {history_len} items")
        
        # 3. Check Timers
        now = time.time()
        last_intervention_ago = now - self.cognitive.last_intervention
        logger.info(f"Last Intervention: {last_intervention_ago:.1f}s ago")
        logger.info(f"Cooldown: {self.cognitive.INTERVENTION_COOLDOWN}s")

        logger.info(f"4. Active Task: {self.cognitive.active_task}")
    
        # 5. Check Observation Buffer
        buffer_len = len(self.cognitive.observation_buffer)
        logger.info(f"5. Observation Buffer: {buffer_len} items")
        if buffer_len > 0:
            buffer_states = [s.name for s in self.cognitive.observation_buffer]
            logger.info(f"   Buffer contents: {buffer_states}")
    
        # 6. Test violation detection
        logger.info("6. Running violation check...")
        
        # 4. Force Curiosity Check (Bypass probability for test?)
        # We can just run the standard check check
        violation, msg = self.cognitive._check_violation()
        
        if violation:
            logger.info(f"VIOLATION/TRIGGER DETECTED: {msg}")
            # Optionally speak it
            # self.tts.speak(msg)
        else:
            logger.info("No violation or trigger active at this moment.")
            
        # 7. Test curiosity check
        logger.info("7. Testing curiosity...")
        if self.cognitive._check_curiosity():
            logger.info("   Curiosity WOULD trigger (80% chance)")
            msg = self.cognitive._generate_curiosity_message()
            logger.info(f"   Message: {msg}")
        else:
            logger.info("   Curiosity would NOT trigger")
    
        logger.info("=== DIAGNOSTIC COMPLETE ===")
    
        # Reset listening state
        self._reset_listening()

    def _test_cognitive_scenarios(self):
        """Test cognitive engine with different scenarios"""
        logger.info("=== TESTING COGNITIVE ENGINE SCENARIOS ===")
    
        test_cases = [
            ("VS Code", "User is writing Python code with syntax highlighting", "Coding"),
            ("Chrome", "User is watching a YouTube video with playback controls", "Entertainment"),
            ("Terminal", "User is looking at error messages and stack traces", "Debugging"),
            ("Slack", "User is in a Zoom meeting with video conference", "Meeting"),
            ("Edge", "User is reading documentation with code examples", "Reading"),
            ("Desktop", "No applications open, just desktop background", "TheVoid"),
        ]
    
        for app, vision, expected_state in test_cases:
            logger.info(f"\nScenario: {app}")
            logger.info(f"Vision: {vision}")
        
            needs, msg = self.cognitive.update_observation(app, vision)
            actual_state = self.cognitive.current_state.name
        
            logger.info(f"Expected: {expected_state}, Got: {actual_state}")
            logger.info(f"Intervention needed: {needs}")
            if msg:
                logger.info(f"Message: {msg}")
        
            time.sleep(0.5)
    
        logger.info("=== SCENARIO TEST COMPLETE ===")
        self._reset_listening()

    def _initial_greeting(self):
        """
        Greets the user based on time of day and name.
        """
        time.sleep(1.0) # Wait for startup
        
        # 1. Get Name
        name = self.profile.profile.get("name", "Sir")
        
        # 2. Get Time of Day
        hour = time.localtime().tm_hour
        if 5 <= hour < 12:
            period = "Morning"
        elif 12 <= hour < 17:
            period = "Afternoon"
        elif 17 <= hour < 22:
            period = "Evening"
        else:
            period = "Night"
            
        greeting = f"Good {period}, {name}."
        
        logger.info(f"Startup Greeting: {greeting}")
        
        # Direct Synthesis (Skip LLM for speed/accuracy on simple greeting)
        # We manually manage state to ensure input gating works if we wanted, 
        # but _synthesize_and_play is blocking mostly. 
        # Actually, let's use the LLM to allow for *slight* personality but enforce the core message.
        # "Say exactly: 'Good Morning, Himanshu.'"
        
        self._commit_turn_proactive(f"[SYSTEM STARTUP]: Say exactly: '{greeting}'. Do not add anything else.")