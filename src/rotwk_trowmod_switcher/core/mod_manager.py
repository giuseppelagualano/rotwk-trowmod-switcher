import logging
import os

from rotwk_trowmod_switcher.config import VERSION_MARKER_FILENAME
from rotwk_trowmod_switcher.core.big_archiver.costants import (
    DEFAULT_ARTS_ARCHIVE_NAME,
    DEFAULT_DATA1_ARCHIVE_NAME,
    DEFAULT_INI_ARCHIVE_NAME,
    DEFAULT_ITLANG_ARCHIVE_NAME,
)

MOD_FILES_TO_REMOVE = [
    DEFAULT_INI_ARCHIVE_NAME,
    DEFAULT_ARTS_ARCHIVE_NAME,
    DEFAULT_DATA1_ARCHIVE_NAME,
    "lang/" + DEFAULT_ITLANG_ARCHIVE_NAME,
    VERSION_MARKER_FILENAME,
]


def remove_mod_files(game_path: str, logger: logging.Logger) -> bool:
    """
    Removes the specific files associated with the TROW Mod from the game installation directory.

    This function attempts to delete a predefined list of files
    associated with the mod. It logs operations and handles common errors
    like file not found or permission issues.

    Args:
        game_path: The absolute path to the main Rise of the Witch-king
                   installation directory.
        logger: The logger instance to use for logging messages.

    Returns:
        True if all target files were successfully removed
        or were already absent. False if an error occurred during
        the removal of any target file/folder (e.g., PermissionError).
    """
    if not game_path or not os.path.isdir(game_path):
        logger.error(f"Invalid game path provided for removal: '{game_path}'")
        return False

    logger.info(f"Starting removal of mod files from: '{game_path}'")

    all_removed_successfully = True  # Flag to track overall success

    for relative_path in MOD_FILES_TO_REMOVE:
        full_path = os.path.join(game_path, relative_path)
        logger.debug(f"Attempting to remove target: '{full_path}'")

        if os.path.exists(full_path):
            try:
                logger.info(f"Removing file: '{full_path}'")
                os.remove(full_path)
                logger.info(f"Successfully removed file: '{full_path}'")

            except FileNotFoundError:
                # Rare if we use os.path.exists() first, but handle for safety (race condition)
                logger.warning(f"File disappeared between check and removal: '{full_path}'")
                # We don't consider this a failure, the goal is for it to be gone
            except PermissionError:
                logger.error(f"Permission error while removing '{full_path}'. Run as administrator?")
                all_removed_successfully = False  # Critical error, operation fails
            except OSError as e:
                # Generic OS error during file/folder operation
                logger.error(f"Operating system error while removing '{full_path}': {e}")
                all_removed_successfully = False
            except Exception as e:
                # Catch any other unexpected exceptions
                logger.exception(f"Unexpected error while removing '{full_path}': {e}")
                all_removed_successfully = False
        else:
            # The file doesn't exist, which is the desired end state
            logger.info(f"Target not found (already removed?): '{full_path}'")
            # This does not count as a failure

    # Final log based on the flag
    if all_removed_successfully:
        logger.info("Mod file removal completed successfully (or files were not present).")
    else:
        logger.error("Mod file removal completed with errors. Check previous logs.")

    return all_removed_successfully
