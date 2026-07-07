import json
import os
import logging

logger = logging.getLogger(__name__)

class ProfileManager:
    """
    Manages long-term user memory via a persistent JSON profile.
    Location: user_profile.json
    """
    def __init__(self, filepath="user_profile.json"):
        self.filepath = filepath
        self.profile = {
            "name": "User",
            "preferences": {},
            "facts": []
        }
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    self.profile = json.load(f)
                logger.info("Profile loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load profile: {e}")
        else:
            logger.info("No profile found. Creating new.")
            self._save()

    def _save(self):
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self.profile, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save profile: {e}")

    def get_context_string(self):
        """Returns a string formatted for the System Prompt."""
        facts = "\n".join([f"- {f}" for f in self.profile.get("facts", [])])
        return f"""
USER PROFILE:
Name: {self.profile.get("name")}
Facts:
{facts}
"""

    def remember_fact(self, fact):
        """Adds a fact to the profile."""
        if fact not in self.profile["facts"]:
            self.profile["facts"].append(fact)
            self._save()
            return True
        return False
        
    def set_name(self, name):
        self.profile["name"] = name
        self._save()
