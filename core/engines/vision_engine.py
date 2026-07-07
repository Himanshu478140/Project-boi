import mss
import cv2
import numpy as np
import base64
import logging
import time

logger = logging.getLogger(__name__)

class VisionEngine:
    def __init__(self):
        # self.sct = mss.mss() # MSS is not thread-safe if shared. Init locally.
        self.camera_index = 0

    def capture_screen(self, monitor_index=0):
        """
        Captures the screen and returns it as a base64 encoded string.
        monitor_index: 0 for all monitors, 1 for primary, etc.
        """
        try:
            with mss.mss() as sct:
                if monitor_index <= 0:
                    monitor = sct.monitors[0] # All monitors combined
                elif monitor_index < len(sct.monitors):
                    monitor = sct.monitors[monitor_index]
                else:
                    logger.warning(f"Monitor index {monitor_index} out of range. Defaulting to primary.")
                    monitor = sct.monitors[1]

                # Capture
                sct_img = sct.grab(monitor)
                
                # Convert to numpy array
                img = np.array(sct_img)
                
                # Convert BGRA to RGB
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                
                return self._encode_image(img)

        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None

    def capture_webcam(self):
        """
        Captures a single frame from the webcam and returns it as base64.
        """
        cap = None
        try:
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                logger.error("Could not open webcam.")
                return None

            # Allow camera to warm up specific to some hardware
            # but for single frame grab, promptness is key. 
            # We might need to discard the first frame or two if auto-exposure is slow.
            ret, frame = cap.read()
            
            if not ret:
                logger.error("Failed to read frame from webcam.")
                return None

            # Convert BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            return self._encode_image(frame)

        except Exception as e:
            logger.error(f"Webcam capture failed: {e}")
            return None
        finally:
            if cap:
                cap.release()

    def _encode_image(self, image_array):
        """
        Encodes a numpy image array to a base64 string (JPEG format).
        """
        try:
            # Convert RGB back to BGR for encoding (OpenCV expects BGR)
            # Actually, imencode expects BGR. My capture methods output RGB for consistency if viewed elsewhere,
            # but for encoding with cv2, we need BGR.
            # Let's fix the flow: Capture -> Convert to BGR (if needed) -> Encode.
            
            # Re-convert to BGR for cv2.imencode
            img_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            
            _, buffer = cv2.imencode('.jpg', img_bgr)
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            return jpg_as_text
            
        except Exception as e:
            logger.error(f"Image encoding failed: {e}")
            return None
