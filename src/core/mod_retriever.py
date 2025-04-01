from git import Repo
from github import Github, UnknownObjectException
import logging
import tempfile

from core.config import DEFAULT_ARCHIVE_NAME
from core.archiver import create_trowmod_ini_big_archive

# --- Logger and Constants --- (Setup logger as before)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_latest_release_str(repo_full_name:str) -> str:
    try:
        with Github() as g:
            logger.info(f"Getting repository: {repo_full_name}")
            repo = g.get_repo(repo_full_name)

            logger.info("Getting latest release information...")
            release = repo.get_latest_release()
            logger.info(f"Found latest release tagged: {release.tag_name}")
    except UnknownObjectException:
        logger.error(f"Repository '{repo_full_name}' or its latest release not found (404). Check name and/or token permissions.")
        return None
    
    return release.tag_name


def update_rotwk_with_latest_mod(repo_full_name:str, game_path: str):
    try:
        # get latest release 
        latest_release = get_latest_release_str(repo_full_name)

        # Clone the repository
        with tempfile.TemporaryDirectory(prefix="pybig_") as temp_dir_str:
            Repo.clone_from(
                url=f"https://github.com/{repo_full_name}",
                to_path=temp_dir_str,
                branch=latest_release
            )
            logger.info(f"Repository cloned successfully {repo_full_name}")

            return create_trowmod_ini_big_archive(
                source_dir_path=temp_dir_str,
                output_dir_path=game_path,
                archive_name=DEFAULT_ARCHIVE_NAME
            )

    except Exception as e:
        logger.error(f"Errore during download: {e}")
        return False
