import requests
from typing import Tuple, Optional
from app.logger import get_logger

logger = get_logger()


class UpdateChecker:
    GITHUB_REPO = "Hossam1104/pos_admin_tool"
    API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

    @staticmethod
    def check_update(current_version: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Checks if a newer version is available.
        Returns: (is_available, download_url, version_tag)
        """
        try:
            logger.info(f"Checking for updates... Current: {current_version}")
            response = requests.get(UpdateChecker.API_URL, timeout=5)
            response.raise_for_status()

            data = response.json()
            latest_tag = data.get("tag_name", "").strip().lstrip("v")
            html_url = data.get("html_url", "")

            if not latest_tag:
                return False, None, None

            # Simple version comparison
            if UpdateChecker._is_newer(current_version, latest_tag):
                logger.info(f"New version found: {latest_tag}")
                return True, html_url, latest_tag

            logger.info("Application is up to date.")
            return False, None, None

        except requests.RequestException as e:
            logger.error(f"Update check failed: {e}")
            return False, None, None
        except Exception as e:
            logger.error(f"Unexpected error checking updates: {e}")
            return False, None, None

    @staticmethod
    def _is_newer(current: str, latest: str) -> bool:
        try:
            c_parts = [int(x) for x in current.split(".")]
            l_parts = [int(x) for x in latest.split(".")]

            # Normalize length
            while len(c_parts) < len(l_parts):
                c_parts.append(0)
            while len(l_parts) < len(c_parts):
                l_parts.append(0)

            return l_parts > c_parts
        except ValueError:
            logger.warning(f"Version parsing failed: {current} vs {latest}")
            return False
