import json
import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


def _str_to_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "y", "on")


@dataclass
class MonitoredSite:
    url: str
    name: Optional[str] = None
    selector: Optional[str] = None
    strip_dynamic_tags: Optional[bool] = None

    @property
    def display_name(self) -> str:
        return self.name if self.name else self.url


@dataclass
class Config:
    # Single URL or comma-separated list of URLs
    target_urls_raw: str = os.getenv("TARGET_URLS", "")
    target_url: str = os.getenv("TARGET_URL", "https://example.com")
    css_selector: Optional[str] = os.getenv("CSS_SELECTOR") or None
    strip_dynamic_tags: bool = _str_to_bool(os.getenv("STRIP_DYNAMIC_TAGS", "true"))
    check_interval_seconds: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "3600"))
    state_file_path: str = os.getenv("STATE_FILE_PATH", "state.json")
    sites_file_path: str = os.getenv("SITES_FILE_PATH", "sites.json")

    # Explicit list of sites (configured dynamically or loaded from file/env)
    sites: List[MonitoredSite] = field(default_factory=list)

    # SMTP Configuration
    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_use_tls: bool = _str_to_bool(os.getenv("SMTP_USE_TLS", "true"))
    smtp_use_ssl: bool = _str_to_bool(os.getenv("SMTP_USE_SSL", "false"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")

    # Notification addresses
    email_sender: str = os.getenv("EMAIL_SENDER", "") or os.getenv("SMTP_USERNAME", "")
    email_recipient: str = os.getenv("EMAIL_RECIPIENT", "")
    email_subject_prefix: str = os.getenv("EMAIL_SUBJECT_PREFIX", "[Web-Listener Alert]")

    def get_sites(self) -> List[MonitoredSite]:
        """
        Returns list of monitored sites from:
        1. Explicitly configured self.sites (e.g. from CLI or programmatic call)
        2. sites_file_path if the JSON file exists
        3. TARGET_URLS comma-separated list from .env
        4. Fallback to TARGET_URL
        """
        if self.sites:
            return self.sites

        # Check if sites.json file exists
        if self.sites_file_path and os.path.exists(self.sites_file_path):
            try:
                with open(self.sites_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        loaded_sites = []
                        for item in data:
                            if isinstance(item, str):
                                loaded_sites.append(MonitoredSite(url=item.strip()))
                            elif isinstance(item, dict) and "url" in item:
                                loaded_sites.append(
                                    MonitoredSite(
                                        url=item["url"].strip(),
                                        name=item.get("name"),
                                        selector=item.get("selector"),
                                        strip_dynamic_tags=item.get("strip_dynamic_tags"),
                                    )
                                )
                        if loaded_sites:
                            return loaded_sites
            except Exception as e:
                import logging
                logging.getLogger("WebListener.Config").warning(
                    "Failed to parse sites file '%s': %s", self.sites_file_path, e
                )

        # Check TARGET_URLS comma-separated list
        if self.target_urls_raw:
            urls = [u.strip() for u in self.target_urls_raw.split(",") if u.strip()]
            if urls:
                return [
                    MonitoredSite(
                        url=u,
                        selector=self.css_selector,
                        strip_dynamic_tags=self.strip_dynamic_tags,
                    )
                    for u in urls
                ]

        # Fallback to single TARGET_URL
        return [
            MonitoredSite(
                url=self.target_url,
                selector=self.css_selector,
                strip_dynamic_tags=self.strip_dynamic_tags,
            )
        ]


def get_config() -> Config:
    return Config()
