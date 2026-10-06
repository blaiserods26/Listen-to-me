import difflib
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import requests
from bs4 import BeautifulSoup
from config import Config, MonitoredSite
from notifier import EmailNotifier

logger = logging.getLogger("WebListener.Monitor")


class WebsiteMonitor:
    def __init__(self, config: Config, notifier: Optional[EmailNotifier] = None):
        self.config = config
        self.notifier = notifier or EmailNotifier(config)
        self.state: Dict[str, dict] = self._load_state()

    def _load_state(self) -> Dict[str, dict]:
        """Load persistent state from state file."""
        if os.path.exists(self.config.state_file_path):
            try:
                with open(self.config.state_file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Error reading state file '%s': %s. Starting with empty state.", self.config.state_file_path, e)
        return {}

    def _save_state(self) -> None:
        """Save persistent state to state file."""
        try:
            dirname = os.path.dirname(self.config.state_file_path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            with open(self.config.state_file_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Error writing state file '%s': %s", self.config.state_file_path, e)

    def fetch_webpage(self, url: str) -> str:
        """Fetch webpage HTML with realistic headers and timeout."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.text

    def extract_monitored_content(
        self,
        html_content: str,
        selector: Optional[str] = None,
        strip_dynamic_tags: Optional[bool] = None,
    ) -> str:
        """Process and extract content based on CSS selector and cleaning options."""
        soup = BeautifulSoup(html_content, "html.parser")

        should_strip = self.config.strip_dynamic_tags if strip_dynamic_tags is None else strip_dynamic_tags
        if should_strip:
            for element in soup(["script", "style", "noscript", "iframe", "svg"]):
                element.decompose()

        active_selector = selector or self.config.css_selector
        if active_selector:
            selected_elements = soup.select(active_selector)
            if not selected_elements:
                logger.warning(
                    "CSS selector '%s' matched no elements on the page. Falling back to whole page text.",
                    active_selector,
                )
                raw_text = soup.get_text()
            else:
                raw_text = "\n".join(el.get_text() for el in selected_elements)
        else:
            raw_text = soup.get_text()

        # Normalize whitespace (strip empty lines, trailing spaces)
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        return "\n".join(lines)

    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA-256 hash of string content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def generate_diff(self, old_content: str, new_content: str) -> str:
        """Generate a concise unified diff between old and new text content."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="previous_content",
            tofile="current_content",
            n=3,
        )
        return "".join(diff)

    def check_site(self, site: MonitoredSite) -> Tuple[bool, str, Optional[str]]:
        """
        Check a single MonitoredSite for changes.
        Returns (has_changed, current_hash, optional_old_hash).
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        logger.info("Checking website: %s (%s)", site.display_name, site.url)

        try:
            raw_html = self.fetch_webpage(site.url)
        except Exception as e:
            logger.error("Failed to fetch %s (%s): %s", site.display_name, site.url, e)
            return False, "", None

        normalized_content = self.extract_monitored_content(
            raw_html,
            selector=site.selector,
            strip_dynamic_tags=site.strip_dynamic_tags,
        )
        current_hash = self.compute_hash(normalized_content)

        url_state = self.state.get(site.url)

        if not url_state:
            # Baseline initialization
            logger.info("Baseline established for %s (%s). Hash: %s", site.display_name, site.url, current_hash)
            self.state[site.url] = {
                "name": site.name,
                "hash": current_hash,
                "content": normalized_content,
                "first_checked": now_iso,
                "last_checked": now_iso,
                "last_changed": now_iso,
            }
            self._save_state()
            return False, current_hash, None

        old_hash = url_state.get("hash")
        old_content = url_state.get("content", "")

        url_state["last_checked"] = now_iso
        if site.name and not url_state.get("name"):
            url_state["name"] = site.name

        if current_hash != old_hash:
            logger.warning(
                "CHANGE DETECTED on %s (%s)! Hash changed from %s to %s",
                site.display_name, site.url, old_hash, current_hash
            )
            diff_text = self.generate_diff(old_content, normalized_content)

            # Send email alert
            self.notifier.send_change_alert(
                url=site.url,
                old_hash=old_hash,
                new_hash=current_hash,
                diff_text=diff_text,
                site_name=site.name,
            )

            # Update saved state
            url_state["hash"] = current_hash
            url_state["content"] = normalized_content
            url_state["last_changed"] = now_iso
            self._save_state()
            return True, current_hash, old_hash
        else:
            logger.info("No change detected for %s (Hash: %s)", site.display_name, current_hash)
            self._save_state()
            return False, current_hash, old_hash

    def check_all(
        self,
        sites: Optional[List[MonitoredSite]] = None
    ) -> List[Tuple[MonitoredSite, bool, str, Optional[str]]]:
        """
        Check all monitored sites.
        Returns list of (site, has_changed, current_hash, old_hash).
        """
        target_sites = sites or self.config.get_sites()
        results = []
        for site in target_sites:
            has_changed, curr_h, old_h = self.check_site(site)
            results.append((site, has_changed, curr_h, old_h))
        return results

    def check_once(self, url: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """Convenience method to check a single URL directly."""
        target_url = url or self.config.target_url
        site = MonitoredSite(
            url=target_url,
            selector=self.config.css_selector,
            strip_dynamic_tags=self.config.strip_dynamic_tags,
        )
        return self.check_site(site)
