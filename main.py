import argparse
import logging
import sys
import time
from config import MonitoredSite, get_config
from monitor import WebsiteMonitor
from notifier import EmailNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("WebListener")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Multi-Website Change Listener: Monitors multiple webpages, hashes their content, and triggers email notifications on changes."
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Single target URL to monitor (overrides TARGET_URL in .env)",
    )
    parser.add_argument(
        "--urls",
        nargs="+",
        help="Multiple target URLs to monitor (space-separated, e.g. --urls https://site1.com https://site2.com)",
    )
    parser.add_argument(
        "--sites-file",
        type=str,
        help="Path to JSON file containing monitored websites configuration (overrides SITES_FILE_PATH in .env)",
    )
    parser.add_argument(
        "--selector",
        type=str,
        help="Default CSS selector to watch specific section (overrides CSS_SELECTOR in .env)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        help="Polling interval in seconds (overrides CHECK_INTERVAL_SECONDS in .env)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check all websites once and exit immediately (useful for cron/Task Scheduler)",
    )
    parser.add_argument(
        "--test-email",
        action="store_true",
        help="Send a test verification email and exit",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = get_config()

    # Apply CLI overrides
    if args.sites_file:
        config.sites_file_path = args.sites_file
    if args.selector is not None:
        config.css_selector = args.selector
    if args.interval:
        config.check_interval_seconds = args.interval

    if args.urls:
        config.sites = [
            MonitoredSite(
                url=u.strip(),
                selector=config.css_selector,
                strip_dynamic_tags=config.strip_dynamic_tags,
            )
            for u in args.urls
            if u.strip()
        ]
    elif args.url:
        config.sites = [
            MonitoredSite(
                url=args.url.strip(),
                selector=config.css_selector,
                strip_dynamic_tags=config.strip_dynamic_tags,
            )
        ]

    notifier = EmailNotifier(config)

    # Test email action
    if args.test_email:
        logger.info("Attempting to send test email to %s...", config.email_recipient)
        success = notifier.send_change_alert(
            url="https://example.com",
            old_hash="test-old-hash-11111111111111111111111111111111",
            new_hash="test-new-hash-22222222222222222222222222222222",
            diff_text="+ Sample line added\n- Sample line removed\n",
            site_name="Test Website",
        )
        if success:
            logger.info("Test email sent successfully!")
            sys.exit(0)
        else:
            logger.error("Failed to send test email. Check your SMTP configuration in .env.")
            sys.exit(1)

    monitor = WebsiteMonitor(config, notifier=notifier)
    monitored_sites = config.get_sites()

    logger.info("=== Multi-Website Listener Initialized ===")
    logger.info("Total Sites Configured: %d", len(monitored_sites))
    for i, s in enumerate(monitored_sites, 1):
        selector_info = f" (Selector: {s.selector})" if s.selector else ""
        logger.info("  [%d] %s -> %s%s", i, s.display_name, s.url, selector_info)

    logger.info("Check Interval: %d seconds", config.check_interval_seconds)
    logger.info("State File: %s", config.state_file_path)
    logger.info("Email Recipient: %s", config.email_recipient or "[Not configured]")

    if args.once:
        logger.info("Executing single pass across all %d website(s)...", len(monitored_sites))
        monitor.check_all(monitored_sites)
        logger.info("Single pass complete.")
        return

    # Continuous monitoring loop
    logger.info("Starting monitoring loop. Press Ctrl+C to terminate.")
    try:
        while True:
            monitor.check_all(monitored_sites)
            time.sleep(config.check_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Listener stopped by user.")


if __name__ == "__main__":
    main()
