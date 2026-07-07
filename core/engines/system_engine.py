import logging
import psutil
import pygetwindow as gw
import time

logger = logging.getLogger(__name__)

class SystemEngine:
    def __init__(self):
        self.last_context = ""
        self.last_update = 0
        self.CACHE_DURATION = 2.0 # Update every 2 seconds max
        
    def get_context(self):
        """
        Returns a formatted string describing the current system state.
        e.g., "ACTIVE WINDOW: 'main.py - VS Code'\nSYSTEM: CPU 12% | RAM 45%"
        """
        now = time.time()
        if now - self.last_update < self.CACHE_DURATION and self.last_context:
            return self.last_context
            
        try:
            # 1. Active Window
            active_window = gw.getActiveWindow()
            if active_window:
                window_title = active_window.title.strip()
                if not window_title:
                    window_title = "Unknown Window"
            else:
                window_title = "Desktop / None"
                
            # 2. System Stats
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            
            context = f"ACTIVE WINDOW: '{window_title}'\nSYSTEM: CPU {cpu}% | RAM {ram}%"
            
            self.last_context = context
            self.last_update = now
            return context
            
        except Exception as e:
            logger.error(f"System Context Error: {e}")
            return "SYSTEM CONTEXT: Unavailable"

    def get_active_app_name(self):
        try:
            win = gw.getActiveWindow()
            return win.title if win else None
        except:
            return None
