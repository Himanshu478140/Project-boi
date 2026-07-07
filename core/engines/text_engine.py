import logging
import uiautomation as auto
import time

logger = logging.getLogger(__name__)

class TextEngine:
    def __init__(self):
        self.last_text = ""
        self.last_update = 0
        self.CACHE_DURATION = 1.0 # Cache for 1 second

    def get_focused_text(self, max_chars=4000):
        """
        Retrieves text from the currently focused UI element.
        Tries ValuePattern, DocumentPattern, then Name.
        """
        now = time.time()
        if now - self.last_update < self.CACHE_DURATION and self.last_text:
            return self.last_text

        try:
            # Get the focused element
            element = auto.GetFocusedControl()
            if not element:
                return ""
            
            text = ""
            
            # Debug Element Info
            logger.info(f"Focused Element: Type={element.ControlTypeName}, Name='{element.Name[:30]}...', ID={element.AutomationId}")

            # 1. Try ValuePattern (Editable text fields, address bars)
            # Use raw pattern ID or the helper method
            if hasattr(element, 'GetValuePattern'):
                 pattern = element.GetValuePattern()
                 if pattern:
                     val = pattern.Value
                     if val:
                         text = val
                         source = "ValuePattern"
            
            # 2. Try DocumentPattern (Browsers, Word) if Value failed or empty
            if not text and hasattr(element, 'GetDocumentPattern'):
                pattern = element.GetDocumentPattern()
                if pattern:
                    # Document selection or full text?
                    # TextPattern is better for range.
                    pass 
            
            # 3. Try TextPattern (More general for documents)
            if not text and hasattr(element, 'GetTextPattern'):
                pattern = element.GetTextPattern()
                if pattern:
                    # Get full document text
                    val = pattern.DocumentRange.GetText(max_chars)
                    if val:
                        text = val
                        source = "TextPattern"
            
            # 4. Fallback: Traverse Children (Deep Search)
            # If the top element has no text, it might be a container (Pane, Document).
            if not text:
                text = self._traverse_children_for_text(element, max_depth=3, max_chars=max_chars)
                if text:
                    source = "ChildrenTraversal"

            # 5. Last Resort: Name
            if not text:
                text = element.Name
                source = "Name"
            
            if text:
                # Clean up
                text = text.strip()
                if len(text) > max_chars:
                    text = text[:max_chars] + "..."
                
                self.last_text = text
                self.last_update = now
                logger.info(f"TextEngine extracted {len(text)} chars from [{source}]: {text[:50]}...")
                return text
                
            return ""

        except Exception as e:
            logger.error(f"TextEngine Error: {e}")
            return ""

    def _traverse_children_for_text(self, element, max_depth=3, max_chars=4000):
        """
        Recursively searches children for text content (TextPattern or Name).
        Helpful when focus is on a container.
        """
        if max_depth == 0:
            return ""
            
        collected_text = []
        total_len = 0
        
        try:
            # Get first child
            child = element.GetFirstChildControl()
            while child:
                # 1. Try TextPattern on Child
                check_val = ""
                if hasattr(child, 'GetTextPattern'):
                    pat = child.GetTextPattern()
                    if pat:
                        check_val = pat.DocumentRange.GetText(max_chars)
                
                # 2. Try ValuePattern on Child
                if not check_val and hasattr(child, 'GetValuePattern'):
                    pat = child.GetValuePattern()
                    if pat:
                        check_val = pat.Value

                # 3. Try Name (if reasonable length)
                if not check_val and child.Name:
                    check_val = child.Name
                
                if check_val:
                    check_val = check_val.strip()
                    if check_val:
                        collected_text.append(check_val)
                        total_len += len(check_val)
                        if total_len >= max_chars:
                            break
                
                # Recurse
                if not check_val: # Only dig deeper if this node didn't yield main text
                    sub_text = self._traverse_children_for_text(child, max_depth - 1, max_chars - total_len)
                    if sub_text:
                        collected_text.append(sub_text)
                        total_len += len(sub_text)
                        
                if total_len >= max_chars:
                    break
                    
                child = child.GetNextSiblingControl()
                
        except Exception:
            pass # Ignore traversal errors
            
        return "\n".join(collected_text)
