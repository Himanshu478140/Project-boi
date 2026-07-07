import os
import logging
import fnmatch
from pathlib import Path

logger = logging.getLogger(__name__)

class FileSystemEngine:
    def __init__(self):
        self.user_home = Path.home()
        self.search_roots = [
            self.user_home / "Documents",
            self.user_home / "Downloads",
            self.user_home / "Desktop",
            self.user_home / "AI PROJECT" # Assuming standard location, can be config'd
        ]
        
    def search(self, query, extension=None, limit=5):
        """
        Searches for files matching 'query' in defined roots.
        Returns list of matches.
        """
        logger.info(f"FileSystem: Searching for '{query}'...")
        matches = []
        
        query = query.lower()
        
        for root in self.search_roots:
            if not root.exists(): 
                continue
                
            for path in root.rglob("*"):
                # Safety/Performance: Skip hidden folders
                if any(part.startswith('.') for part in path.parts):
                    continue
                    
                if not path.is_file():
                    continue
                    
                if query in path.name.lower():
                    if extension and not path.name.endswith(extension):
                        continue
                        
                    matches.append(str(path))
                    if len(matches) >= limit:
                        return matches
        return matches

    def open_file(self, path):
        """Opens the file using the default OS application."""
        try:
            os.startfile(path)
            logger.info(f"Opened file: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to open file {path}: {e}")
            return False
