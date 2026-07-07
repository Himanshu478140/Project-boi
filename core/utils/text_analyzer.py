
import re
import logging

logger = logging.getLogger(__name__)

class TextAnalyzer:
    """
    Analyzes partial transcripts to estimate semantic completeness.
    Used to adjust VAD silence thresholds dynamically.
    """
    
    # Status Enums
    COMPLETE = "COMPLETE"     # Likely finished -> Short Pause OK
    INCOMPLETE = "INCOMPLETE" # Explicitly unfinished -> Wait longer
    FILLER = "FILLER"         # Just a filler -> Ignore timeout (Reset)
    NEUTRAL = "NEUTRAL"       # Unsure -> Use Default
    
    # Heuristics
    TRAILING_CONNECTORS = ["and", "but", "or", "so", "because", "if", "then", "when", "while"]
    
    @staticmethod
    def analyze(text):
        """
        Returns: (status, confidence_reason)
        """
        if not text:
            return TextAnalyzer.NEUTRAL, "Empty"
            
        clean_text = text.strip().lower()
        words = clean_text.split()
        
        if not words:
            return TextAnalyzer.NEUTRAL, "Empty"
            
        last_word = words[-1]
        # remove punctuation from last word for connector check
        last_word_alnum = re.sub(r'[^\w\s]', '', last_word) 
        
        if last_word_alnum in TextAnalyzer.TRAILING_CONNECTORS:
            return TextAnalyzer.INCOMPLETE, f"Connector: {last_word_alnum}"
            
        # Detect Short Fillers/Hesitation (Start of turn)
        # "Hmm", "Uh", "One" (often misheard), "Right"
        if len(words) <= 2 and clean_text in ["hmm", "uh", "um", "one", "right", "yeah", "i think", "you", "but", "so", "like"]:
             return TextAnalyzer.FILLER, "Pure Filler"
            
        # Discourse Markers (Multi-word check)
        # "I think", "You know", "Like"
        clean_suffix = clean_text[-15:] # Check last few chars
        if any(marker in clean_suffix for marker in ["i think", "you know", "i mean", "sort of", "kind of"]):
             return TextAnalyzer.INCOMPLETE, "Discourse Marker"
            
        # Ends with comma? "Actually,"
        if text.strip().endswith(","):
             return TextAnalyzer.INCOMPLETE, "Trailing Comma"

        # 2. COMPLETE CHECK (Strong Signal)
        # Needs explicit punctuation AND sufficient length
        has_punctuation = text.strip()[-1] in ['.', '?', '!']
        
        if has_punctuation:
            if len(words) < 2:
                # "Why?" is complete, but "The." is liable to be a partial fragment.
                # Let's be safe. If it's a single word, treat as NEUTRAL unless it's a specific command.
                return TextAnalyzer.NEUTRAL, "Short w/ Punct"
            return TextAnalyzer.COMPLETE, "Punctuation"
            
        # 3. Default
        return TextAnalyzer.NEUTRAL, "No signal"
