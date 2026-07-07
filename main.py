import logging
import time
import sys
from core.pipeline.orchestrator import Orchestrator

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("MAIN")

def main():
    logger.info("Initializing Voice Assistant...")
    
    orchestrator = None
    
    try:
        orchestrator = Orchestrator()
        orchestrator.start()
        
        logger.info("System Running. Press Ctrl+C to stop.")
        
        # Keep main thread alive
        while True:
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        logger.info("Keyboard Interrupt received. Shutting down...")
    except Exception as e:
        logger.critical(f"Fatal Error: {e}", exc_info=True)
    finally:
        if orchestrator:
            orchestrator.stop()
        logger.info("Goodbye.")

if __name__ == "__main__":
    main()
