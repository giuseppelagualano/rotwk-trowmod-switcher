# src/main.py
import logging
import sys

# --- Import the GUI application runner ---
try:
    from rotwk_trowmod_switcher.config import __APP_NAME__  # Get app name for logger
    from rotwk_trowmod_switcher.gui.app import run_gui
except ImportError as e:
    # Basic fallback if imports fail (e.g., structure not created yet)
    print(
        "Error: Could not import application components. Check project structure and paths.",
        file=sys.stderr,
    )
    print(f"Details: {e}", file=sys.stderr)
    k = input("press to close")
    # sys.exit(1)

# --- Basic Logging Setup (before GUI starts) ---
# Configure basic console logging until the GUI handler takes over
log_format = "%(asctime)s - %(levelname)s - [%(name)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format)
logger = logging.getLogger(__APP_NAME__)  # Use app name for root logger

# --- Entry Point ---
if __name__ == "__main__":
    logger.info("Starting application entry point...")
    try:
        run_gui()  # Call the function that builds and runs the GUI
        logger.info("GUI main loop exited.")
    except Exception as e:
        logger.critical(f"An unhandled exception occurred in the GUI: {e}", exc_info=True)
        # Consider showing a simple error message box here if possible,
        # although tkinter might not be available if run_gui failed early.
        # sys.exit(1)  # Exit with error code
