import json
import logging
import os
import shutil
import ssl
import tempfile
import urllib.error
import urllib.request
import zipfile

import certifi

from rotwk_trowmod_switcher.core.big_archiver.archiver import create_big_archives

# --- Logger Setup ---
# Configure logging for informative output
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_latest_release_tag(repo_full_name: str) -> str:
    """
    Fetches the tag name of the latest release of a GitHub repository
    using the GitHub REST API with standard libraries.

    Args:
        repo_full_name: The repository name in 'owner/repo' format.

    Returns:
        The tag name string if successful, None otherwise.
    """
    # Construct the GitHub API URL for the latest release
    api_url = f"https://api.github.com/repos/{repo_full_name}/releases/latest"
    logger.info(f"Fetching latest release info from: {api_url}")

    try:
        # Use standard library's urllib to make the HTTP GET request
        # Set a User-Agent header, as GitHub API requires it
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        request = urllib.request.Request(api_url, headers={"User-Agent": "Python-Urllib-Client"})
        with urllib.request.urlopen(request, context=ssl_context) as response:
            # Check for successful response (HTTP 200 OK)
            if response.status == 200:
                # Read the response body and decode it from bytes to string
                response_body = response.read().decode("utf-8")
                # Parse the JSON response into a Python dictionary
                data = json.loads(response_body)
                # Extract the 'tag_name' field
                tag_name = data.get("tag_name")
                if tag_name:
                    logger.info(f"Found latest release tagged: {tag_name}")
                    return tag_name
                else:
                    # Log error if 'tag_name' is missing in the response
                    logger.error("Could not find 'tag_name' in the API response.")
                    return None
            else:
                # Log error for non-200 responses (although urlopen usually raises HTTPError)
                logger.error(f"Failed to fetch latest release info. Status code: {response.status}")
                return None
    except urllib.error.HTTPError as e:
        # Handle specific HTTP errors
        logger.error(f"HTTP Error fetching release info for '{repo_full_name}': {e.code} {e.reason}")
        if e.code == 404:
            logger.error("Repository or latest release not found. Check the repository name.")
        elif e.code == 403:
            # 403 can be due to rate limiting or missing permissions for private repos
            logger.error("Access forbidden. This could be due to API rate limits or the repository being private.")
        elif e.code == 401:
            logger.error("Authentication required. The repository might be private.")
        # Read the response body even for errors, it might contain useful info
        error_details = e.read().decode("utf-8")
        logger.error(f"GitHub API response body: {error_details}")
        return None
    except json.JSONDecodeError:
        # Handle errors parsing the JSON response
        logger.error("Failed to parse JSON response from GitHub API.")
        return None
    except Exception as e:
        # Catch any other unexpected errors (network issues, etc.)
        logger.error(
            f"An unexpected error occurred while fetching release info: {e}",
            exc_info=True,
        )
        return None


def update_rotwk_with_latest_mod(repo_full_name: str, game_path: str) -> bool:
    """
    Downloads the latest release source code of a GitHub mod, extracts it,
    and processes it using standard Python libraries.

    Args:
        repo_full_name: The repository name in 'owner/repo' format.
        game_path: The path where the final archive should be placed.

    Returns:
        True if the update and archiving process was successful, False otherwise.
    """
    try:
        # 1. Get the latest release tag using the GitHub API
        latest_tag = get_latest_release_tag(repo_full_name)
        if not latest_tag:
            logger.error("Could not determine the latest release tag. Aborting update.")
            return False

        # 2. Construct the download URL for the zip archive of the tagged release
        # GitHub provides zip archives at this standard URL format
        zip_url = f"https://github.com/{repo_full_name}/archive/refs/tags/{latest_tag}.zip"
        logger.info(f"Attempting to download source code archive from: {zip_url}")

        # 3. Create a temporary directory to download and extract the archive
        # 'with' statement ensures the directory is cleaned up automatically
        with tempfile.TemporaryDirectory(prefix="gh_download_") as temp_dir:
            logger.info(f"Created temporary directory: {temp_dir}")
            # Define the path where the zip file will be saved within the temp directory
            zip_file_path = os.path.join(temp_dir, f"{latest_tag.replace('/', '_')}.zip")  # Sanitize tag name for filename

            # 4. Download the zip file using standard urllib
            try:
                logger.info(f"Downloading to: {zip_file_path}")

                # Create the SSL context using certifi
                ssl_context = ssl.create_default_context(cafile=certifi.where())

                # Create the request object (needed if you want to set headers like User-Agent)
                request = urllib.request.Request(zip_url, headers={"User-Agent": "Python-Urllib-Client"})

                # Open the URL with urlopen using the SSL context
                with (
                    urllib.request.urlopen(request, context=ssl_context) as response,
                    open(zip_file_path, "wb") as out_file,
                ):
                    # Copy the content from the response to the local file
                    # shutil.copyfileobj reads in chunks, efficient for large files
                    shutil.copyfileobj(response, out_file)

                logger.info(f"Successfully downloaded archive to: {zip_file_path}")

            except urllib.error.HTTPError as e:
                logger.error(f"HTTP Error downloading archive from '{zip_url}': {e.code} {e.reason}")
                return False
            except urllib.error.URLError as e:  # Add URLError handling for SSL
                logger.error(
                    f"URL Error downloading archive from '{zip_url}': {e.reason}",
                    exc_info=True,
                )
                if isinstance(e.reason, ssl.SSLError):
                    logger.error("SSL Error detail: Failed to verify certificate. Check system/certifi certificates.")
                return False
            except Exception as e:
                logger.error(f"Failed to download archive: {e}", exc_info=True)
                return False

            # 5. Extract the contents of the downloaded zip file
            try:
                logger.info(f"Extracting archive '{zip_file_path}' to '{temp_dir}'")
                with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
                logger.info(f"Successfully extracted archive in: {temp_dir}")
            except zipfile.BadZipFile:
                # Handle cases where the downloaded file is corrupted or not a zip file
                logger.error(f"Downloaded file '{zip_file_path}' is not a valid zip archive.")
                return False
            except Exception as e:
                # Handle other potential extraction errors
                logger.error(f"Failed to extract archive: {e}", exc_info=True)
                return False

            # 6. Find the actual extracted content directory path
            # GitHub zip archives usually contain a single top-level folder named like 'repo-tag'
            # We need the path *inside* this folder to pass to the archiver.
            extracted_items = os.listdir(temp_dir)
            # Filter out the zip file itself, leaving potential directories
            potential_dirs = [item for item in extracted_items if os.path.isdir(os.path.join(temp_dir, item))]

            source_content_path = None
            if len(potential_dirs) == 1:
                # If there's exactly one directory, assume it's the correct one
                source_content_path = os.path.join(temp_dir, potential_dirs[0])
                logger.info(f"Found extracted content directory: {source_content_path}")
            elif len(potential_dirs) > 1:
                # If multiple directories exist, try to guess based on repo name and tag
                # This is less common for standard GitHub tag archives
                repo_name = repo_full_name.split("/")[-1]
                # Look for directories starting with the repo name
                matching_dirs = [d for d in potential_dirs if d.startswith(repo_name)]
                if len(matching_dirs) == 1:
                    source_content_path = os.path.join(temp_dir, matching_dirs[0])
                    logger.warning(f"Multiple directories found, heuristically selected: {source_content_path}")
                else:
                    logger.error(f"Could not uniquely determine the extracted content directory among multiple options in {temp_dir}. Contents: {extracted_items}")
                    return False
            else:
                # If no directory was found after extraction (unexpected)
                logger.error(f"No directory found after extraction in {temp_dir}. Contents: {extracted_items}")
                return False

            # 7. Call the original archiving function with the path to the extracted source code
            if source_content_path:
                return create_big_archives(
                    source_content_path=source_content_path,
                    game_path=game_path,
                    logger=logger,
                )

            else:
                # Should not happen if logic above is correct, but handle defensively
                logger.error("Failed to determine source content path for archiving.")
                return False

    except Exception as e:
        # Catch-all for any unexpected errors during the overall process
        logger.error(
            f"An unexpected error occurred during the update process: {e}",
            exc_info=True,
        )
        return False
