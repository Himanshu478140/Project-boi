import re
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class SpeechChunk:
    text: str
    speed: float = 1.0
    volume_gain: float = 1.0
    pause_after_ms: int = 0
    intent: str = "neutral"

class ProsodyEngine:
    """
    Heuristic Engine to control Voice Prosody (Speed, Volume, Flow).
    """
    
    # Intent Profiles
    PROFILES = {
        "neutral": {"speed": 1.0, "vol": 1.0},
        "casual": {"speed": 1.1, "vol": 0.9},        # Talker default
        "explanation": {"speed": 0.9, "vol": 1.0},    # Planner default
        "confirmation": {"speed": 1.2, "vol": 0.8},   # "Okay", "Got it"
        "important": {"speed": 0.85, "vol": 1.05}     # Emphasis
    }
    
    # Pause Rules (ms)
    PAUSES = {
        ",": 80,
        ".": 300,
        "?": 300,
        "!": 300,
        "...": 500,
        ":": 150,
        ";": 150
    }

    @staticmethod
    def process(text, intent="neutral"):
        """
        Converts raw text into a list of SpeechChunks with applied prosody.
        """
        profile = ProsodyEngine.PROFILES.get(intent, ProsodyEngine.PROFILES["neutral"])
        base_speed = profile["speed"]
        base_vol = profile["vol"]
        
        chunks = []
        
        # Split by punctuation but keep delimiters
        # Regex: Split on (. ? ! , : ;), keeping them.
        raw_segments = re.split(r'([.,?!:;]+)', text)
        
        # Re-assemble text + punct
        segments = []
        current = ""
        for seg in raw_segments:
            if re.match(r'^[.,?!:;]+$', seg):
                current += seg
                segments.append(current)
                current = ""
            else:
                current += seg
                
        if current:
            segments.append(current)
            
        # Create Chunks
        total_segments = len(segments)
        
        for i, seg in enumerate(segments):
            clean_seg = seg.strip()
            if not clean_seg:
                continue
                
            # Determine Pause from trailing punctuation
            pause_ms = 0
            for punct, ms in ProsodyEngine.PAUSES.items():
                if clean_seg.endswith(punct):
                    pause_ms = ms
                    break
            
            # Sentence Ending Logic (Energy Drop)
            # If it looks like a full stop, drop volume slightly at the end?
            # Actually, per requirements: "Slight volume drop at sentence endings"
            # We apply this to the chunk's volume.
            
            chunk_vol = base_vol
            chunk_speed = base_speed
            
            if clean_seg.endswith(".") or clean_seg.endswith("!"):
                chunk_vol *= 0.9 # Energy drop
                
            # Create Chunk
            chunk = SpeechChunk(
                text=clean_seg,
                speed=chunk_speed,
                volume_gain=chunk_vol,
                pause_after_ms=pause_ms,
                intent=intent
            )
            chunks.append(chunk)
            
        return chunks
