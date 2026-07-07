import logging
from enum import Enum
import os

logger = logging.getLogger(__name__)

class PermissionLevel(Enum):
    AUTO = "auto"          # Allow immediately
    ASK_USER = "ask_user"  # Require explicit user confirmation
    NEVER = "never"        # Block always

class SecurityEngine:
    """
    Gatekeeper for Jarvis.
    Validates actions against a set of safety rules.
    """
    def __init__(self):
        self.rules = {
            "search": PermissionLevel.AUTO,
            "read": PermissionLevel.AUTO,
            "highlight": PermissionLevel.AUTO, # Browser
            "open": PermissionLevel.ASK_USER, # Default to ask for open
            "delete": PermissionLevel.ASK_USER,
            "write": PermissionLevel.ASK_USER,
            "execute": PermissionLevel.ASK_USER,
        }
        
        # Extensions that are generally safe to open
        self.SAFE_EXTENSIONS = {
            ".txt", ".md", ".log", ".json", ".py", ".html", 
            ".css", ".js", ".pdf", ".png", ".jpg", ".jpeg"
        }

    def validate(self, action: str, target: str = "") -> PermissionLevel:
        """
        Determines the permission level for a given action on a target.
        """
        level = self.rules.get(action, PermissionLevel.ASK_USER)
        
        # Refine 'open' based on extension
        if action == "open" and target:
            _, ext = os.path.splitext(target)
            if ext.lower() in self.SAFE_EXTENSIONS:
                return PermissionLevel.AUTO
            else:
                # .exe, .bat, unknown -> ASK_USER
                return PermissionLevel.ASK_USER
                
        return level

    def check_authorization(self, action: str, target: str = "") -> bool:
        """
        Simple boolean check (wrapper).
        Returns True if AUTO, False if ASK/NEVER.
        """
        return self.validate(action, target) == PermissionLevel.AUTO
