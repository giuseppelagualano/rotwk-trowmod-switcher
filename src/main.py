# src/main.py
import sys
import os
import logging

# --- Add src directory to Python path ---
# This allows importing 'core' and 'gui' directly.
# Adjust if your execution context handles this differently.
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# --- Import the GUI application runner ---
try:
    from gui.app import run_gui
    from core.config import __APP_NAME__ # Get app name for logger
except ImportError as e:
    # Basic fallback if imports fail (e.g., structure not created yet)
    print(f"Error: Could not import application components. Check project structure and paths.", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    sys.exit(1)

# --- Basic Logging Setup (before GUI starts) ---
# Configure basic console logging until the GUI handler takes over
log_format = '%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)
logger = logging.getLogger(__APP_NAME__) # Use app name for root logger

# --- Entry Point ---
if __name__ == "__main__":
    logger.info("Starting application entry point...")
    try:
        run_gui() # Call the function that builds and runs the GUI
        logger.info("GUI main loop exited.")
    except Exception as e:
        logger.critical(f"An unhandled exception occurred in the GUI: {e}", exc_info=True)
        # Consider showing a simple error message box here if possible,
        # although tkinter might not be available if run_gui failed early.
        sys.exit(1) # Exit with error code