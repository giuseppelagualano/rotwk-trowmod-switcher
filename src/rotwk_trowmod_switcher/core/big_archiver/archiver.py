# core/archiver.py
import json
import logging
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from pyBIG import Archive

from rotwk_trowmod_switcher.config import VERSION_MARKER_FILENAME
from rotwk_trowmod_switcher.core.big_archiver.costants import (
    DEFAULT_ARTS_ARCHIVE_NAME,
    DEFAULT_DATA1_ARCHIVE_NAME,
    DEFAULT_INI_ARCHIVE_NAME,
    DEFAULT_ITLANG_ARCHIVE_NAME,
)
from rotwk_trowmod_switcher.core.utils import remove_trailing_slashes

logger = logging.getLogger(__name__)


def create_trowmod_ini_big_archive(source_dir_path: str, output_dir_path: str, archive_name: str) -> bool:
    output_dir_path = remove_trailing_slashes(output_dir_path)
    source_dir_path = remove_trailing_slashes(source_dir_path)
    archive_path = output_dir_path + "/" + archive_name

    try:
        logger.info(f"Creating BIG archive from directory: {source_dir_path}")

        with tempfile.TemporaryDirectory(prefix="pybig_ini_") as temp_staging_dir_str:
            logger.debug(f"Using temporary directory for staging ini archive: {temp_staging_dir_str}")

            logger.info(f"Copying '{source_dir_path}' to '{temp_staging_dir_str}'...")
            shutil.copytree(
                source_dir_path + "/data",
                temp_staging_dir_str + "/data",
                dirs_exist_ok=True,
            )
            logger.debug("Copy complete.")

            logger.info(f"Creating INI BIG archive from directory: {temp_staging_dir_str}")

            archive = Archive.from_directory(temp_staging_dir_str)

            logger.info(f"Saving archive to: {archive_path}")
            archive.save(archive_path)

            logger.info(f"Archive created successfully: {archive_path}")

        return True

    except OSError as e:
        logger.error(f"OS error during archive creation: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during archive creation: {e}", exc_info=True)
        return False


def create_trowmod_arts_big_archive(source_dir_path: str, output_dir_path: str, archive_name: str) -> bool:
    output_dir_path = remove_trailing_slashes(output_dir_path)
    source_dir_path = remove_trailing_slashes(source_dir_path)
    archive_path = output_dir_path + "/" + archive_name

    logger.info("Disable old asset.dat renaming it to asset.dat.disabled...")
    try:
        os.replace(output_dir_path + "/asset.dat", output_dir_path + "/asset.dat.disabled")
    except FileNotFoundError:
        logger.warning("asset.dat not found, skipping renaming.")

    logger.info("Insert new asset.dat from mod...")
    shutil.copyfile(source_dir_path + "/arts/asset.dat", output_dir_path + "/asset.dat")

    try:
        logger.info(f"Creating BIG archive from directory: {source_dir_path}")

        with tempfile.TemporaryDirectory(prefix="pybig_arts_") as temp_staging_dir_str:
            logger.debug(f"Using temporary directory for staging arts archive: {temp_staging_dir_str}")

            logger.info(f"Copying '{source_dir_path}' to '{temp_staging_dir_str}'...")
            shutil.copytree(source_dir_path + "/arts", temp_staging_dir_str, dirs_exist_ok=True)
            logger.debug("Copy complete.")

            logger.info(f"Creating Arts BIG archive from directory: {temp_staging_dir_str}")

            archive = Archive.from_directory(temp_staging_dir_str)

            logger.info(f"Saving archive to: {archive_path}")
            archive.save(archive_path)

            logger.info(f"Archive created successfully: {archive_path}")

        return True

    except OSError as e:
        logger.error(f"OS error during archive creation: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during archive creation: {e}", exc_info=True)
        return False


def create_trowmod_itlang_big_archive(source_dir_path: str, output_dir_path: str, archive_name: str) -> bool:
    output_dir_path = remove_trailing_slashes(output_dir_path)
    source_dir_path = remove_trailing_slashes(source_dir_path)
    archive_path = output_dir_path + "/lang/" + archive_name

    try:
        logger.info(f"Creating BIG archive from directory: {source_dir_path}")

        with tempfile.TemporaryDirectory(prefix="pybig_lang_") as temp_staging_dir_str:
            logger.debug(f"Using temporary directory for staging arts archive: {temp_staging_dir_str}")

            logger.info(f"Copying '{source_dir_path}' to '{temp_staging_dir_str}'...")
            shutil.copytree(source_dir_path + "/lang", temp_staging_dir_str, dirs_exist_ok=True)
            logger.debug("Copy complete.")

            logger.info(f"Creating IT Lang BIG archive from directory: {temp_staging_dir_str}")

            archive = Archive.from_directory(temp_staging_dir_str)

            logger.info(f"Saving archive to: {archive_path}")
            archive.save(archive_path)

            logger.info(f"Archive created successfully: {archive_path}")

        return True

    except OSError as e:
        logger.error(f"OS error during archive creation: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during archive creation: {e}", exc_info=True)
        return False


def create_trowmod_data1_big_archive(source_dir_path: str, output_dir_path: str, archive_name: str) -> bool:
    output_dir_path = remove_trailing_slashes(output_dir_path)
    source_dir_path = remove_trailing_slashes(source_dir_path)
    archive_path = output_dir_path + "/" + archive_name

    try:
        logger.info(f"Creating BIG archive from directory: {source_dir_path}")

        with tempfile.TemporaryDirectory(prefix="pybig_data1_") as temp_staging_dir_str:
            logger.debug(f"Using temporary directory for staging arts archive: {temp_staging_dir_str}")

            logger.info(f"Copying '{source_dir_path}' to '{temp_staging_dir_str}'...")
            shutil.copytree(source_dir_path + "/scripts", temp_staging_dir_str, dirs_exist_ok=True)
            logger.debug("Copy complete.")

            logger.info(f"Creating Data1 BIG archive from directory: {temp_staging_dir_str}")

            archive = Archive.from_directory(temp_staging_dir_str)

            logger.info(f"Saving archive to: {archive_path}")
            archive.save(archive_path)

            logger.info(f"Archive created successfully: {archive_path}")

        return True

    except OSError as e:
        logger.error(f"OS error during archive creation: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during archive creation: {e}", exc_info=True)
        return False


def execute_and_log_operations(
    operations: list[tuple[Callable[..., bool], dict[str, Any]]],
    common_args: dict[str, Any],
    logger_instance: logging.Logger,
    start_message: str = "Starting operations...",
    success_message: str = "All operations completed successfully.",
    failure_message: str = "One or more operations failed.",
) -> bool:
    """
    Executes a list of functions, checks if all succeeded, and logs the results.

    Args:
        operations: A list of tuples. Each tuple contains:
                    - The function to call (must return a bool).
                    - A dictionary with the specific arguments for that function.
        common_args: A dictionary with arguments common to all functions.
        logger_instance: The logger instance to use.
        start_message: Message to log at the beginning.
        success_message: Message to log if all operations succeed.
        failure_message: Message to log if at least one operation fails.

    Returns:
        True if all operations were successful, False otherwise.
    """
    logger_instance.info(start_message)
    all_successful = True
    results = []

    for func, specific_args in operations:
        # Merge common and specific arguments
        # Specific args override common ones in case of key conflicts
        call_args = {**common_args, **specific_args}
        try:
            # Call the function with the combined arguments
            success = func(**call_args)
            results.append(success)
            if not success:
                logger_instance.warning(f"Operation {func.__name__} failed.")
                all_successful = False
        except Exception as e:
            logger_instance.error(f"Exception during operation {func.__name__}: {e}", exc_info=True)
            results.append(False)
            all_successful = False
            # You might decide to break here if a critical operation fails
            # break

    if all_successful:
        logger_instance.info(success_message)
    else:
        logger_instance.error(failure_message)

    return all_successful


def create_big_archives(source_content_path: str, game_path: str, logger: logging.Logger, mod_version: str) -> bool:
    """
    Creates the necessary .big archives using the generic function, parallelizing the operations while keeping logs ordered.
    """
    start_time = time.time()  # Start the timer
    # Define the operations to execute
    archive_operations = [
        (create_trowmod_ini_big_archive, {"archive_name": DEFAULT_INI_ARCHIVE_NAME}),
        (create_trowmod_arts_big_archive, {"archive_name": DEFAULT_ARTS_ARCHIVE_NAME}),
        (
            create_trowmod_itlang_big_archive,
            {"archive_name": DEFAULT_ITLANG_ARCHIVE_NAME},
        ),
        (
            create_trowmod_data1_big_archive,
            {"archive_name": DEFAULT_DATA1_ARCHIVE_NAME},
        ),
    ]

    # Define the common arguments
    common_arguments = {
        "source_dir_path": source_content_path,
        "output_dir_path": game_path,
    }

    logger.info("Proceeding to create the big archives...")

    results = []
    all_successful = True

    # Use ThreadPoolExecutor for parallel execution
    with ThreadPoolExecutor() as executor:
        future_to_operation = {executor.submit(func, **{**common_arguments, **specific_args}): (func, specific_args) for func, specific_args in archive_operations}

        for future in as_completed(future_to_operation):
            func, specific_args = future_to_operation[future]
            try:
                success = future.result()
                results.append(success)
                if success:
                    logger.info(f"Operation {func.__name__} completed successfully.")
                else:
                    logger.warning(f"Operation {func.__name__} failed.")
                    all_successful = False
            except Exception as e:
                logger.error(f"Exception during operation {func.__name__}: {e}", exc_info=True)
                results.append(False)
                all_successful = False

    if all_successful:
        logger.info("Archives creation reported success.")
    else:
        logger.error("Archives creation reported failure.")

    if all_successful:
        # --- Write the version marker file as JSON ---
        marker_file_path = os.path.join(game_path, VERSION_MARKER_FILENAME)
        logger.info(f"Writing version marker JSON to: {marker_file_path}")
        try:
            # Prepare data as a dictionary
            version_data = {
                "version": mod_version,
            }
            # Write dictionary as JSON
            with open(marker_file_path, "w", encoding="utf-8") as f:
                json.dump(version_data, f, indent=4, ensure_ascii=False)  # Use indent for readability
            logger.info("Version marker JSON file written successfully.")
        except OSError as e:
            logger.error(f"Failed to write version marker JSON file '{marker_file_path}': {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred writing version marker JSON: {e}", exc_info=True)
            return False

    elapsed_time = time.time() - start_time  # Calculate elapsed time
    logger.debug(f"Time elapsed for creating big archives: {elapsed_time:.2f} seconds")
    return all_successful
