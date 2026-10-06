import json
import os
import tempfile
from unittest.mock import MagicMock
import pytest
from config import Config, MonitoredSite
from monitor import WebsiteMonitor
from notifier import EmailNotifier


@pytest.fixture
def temp_config():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        state_path = tf.name
    
    cfg = Config(
        target_url="https://example.com/test",
        css_selector=None,
        strip_dynamic_tags=True,
        check_interval_seconds=60,
        state_file_path=state_path,
        smtp_server="smtp.example.com",
        smtp_port=587,
        smtp_username="test@example.com",
        smtp_password="password",
        email_sender="test@example.com",
        email_recipient="notify@example.com",
    )
    yield cfg
    if os.path.exists(state_path):
        os.remove(state_path)


def test_hash_calculation():
    text1 = "Hello World"
    text2 = "Hello World"
    text3 = "Hello World!"
    h1 = WebsiteMonitor.compute_hash(text1)
    h2 = WebsiteMonitor.compute_hash(text2)
    h3 = WebsiteMonitor.compute_hash(text3)

    assert len(h1) == 64
    assert h1 == h2
    assert h1 != h3


def test_extract_monitored_content_strips_scripts(temp_config):
    monitor = WebsiteMonitor(temp_config)
    raw_html = """
    <html>
        <head>
            <script>console.log('dynamic timestamp: ' + Date.now());</script>
            <style>body { color: red; }</style>
        </head>
        <body>
            <h1>Main Title</h1>
            <p>Important announcement.</p>
        </body>
    </html>
    """
    content = monitor.extract_monitored_content(raw_html)
    assert "console.log" not in content
    assert "color: red" not in content
    assert "Main Title" in content
    assert "Important announcement." in content


def test_extract_with_css_selector(temp_config):
    temp_config.css_selector = "#announcements"
    monitor = WebsiteMonitor(temp_config)
    raw_html = """
    <div>
        <header>Header content</header>
        <div id="announcements">Notice: System update scheduled.</div>
        <footer>Footer timestamp 12345</footer>
    </div>
    """
    content = monitor.extract_monitored_content(raw_html)
    assert content == "Notice: System update scheduled."


def test_monitor_lifecycle_baseline_and_change_detection(temp_config):
    mock_notifier = MagicMock(spec=EmailNotifier)
    monitor = WebsiteMonitor(temp_config, notifier=mock_notifier)

    # Initial check (Baseline)
    monitor.fetch_webpage = MagicMock(return_value="<html><body>Version 1</body></html>")
    has_changed, curr_hash, old_hash = monitor.check_once()

    assert not has_changed
    assert old_hash is None
    assert curr_hash is not None
    assert not mock_notifier.send_change_alert.called

    # Second check (No Change)
    has_changed, curr_hash2, old_hash2 = monitor.check_once()
    assert not has_changed
    assert curr_hash2 == curr_hash
    assert old_hash2 == curr_hash
    assert not mock_notifier.send_change_alert.called

    # Third check (Change Occurs!)
    monitor.fetch_webpage = MagicMock(return_value="<html><body>Version 2 - Updated!</body></html>")
    has_changed, curr_hash3, old_hash3 = monitor.check_once()

    assert has_changed
    assert curr_hash3 != curr_hash
    assert old_hash3 == curr_hash
    assert mock_notifier.send_change_alert.called

    # Verify notifier arguments
    call_args = mock_notifier.send_change_alert.call_args[1]
    assert call_args["url"] == "https://example.com/test"
    assert call_args["old_hash"] == curr_hash
    assert call_args["new_hash"] == curr_hash3
    assert "Version 2 - Updated!" in call_args["diff_text"]


def test_multi_website_monitoring(temp_config):
    mock_notifier = MagicMock(spec=EmailNotifier)
    monitor = WebsiteMonitor(temp_config, notifier=mock_notifier)

    site1 = MonitoredSite(url="https://site1.com", name="Site One")
    site2 = MonitoredSite(url="https://site2.com", name="Site Two")
    sites = [site1, site2]

    # Baseline for both sites
    def mock_fetch(url):
        if url == "https://site1.com":
            return "<html><body>Site 1 original content</body></html>"
        return "<html><body>Site 2 original content</body></html>"

    monitor.fetch_webpage = MagicMock(side_effect=mock_fetch)
    results = monitor.check_all(sites)

    assert len(results) == 2
    assert results[0][1] is False  # Site 1 baseline
    assert results[1][1] is False  # Site 2 baseline
    assert mock_notifier.send_change_alert.call_count == 0

    # Next check: Site 1 changes, Site 2 stays the same
    def mock_fetch_update(url):
        if url == "https://site1.com":
            return "<html><body>Site 1 MODIFIED content!</body></html>"
        return "<html><body>Site 2 original content</body></html>"

    monitor.fetch_webpage = MagicMock(side_effect=mock_fetch_update)
    results2 = monitor.check_all(sites)

    assert results2[0][1] is True   # Site 1 changed!
    assert results2[1][1] is False  # Site 2 unchanged

    # Notification sent only for Site 1
    assert mock_notifier.send_change_alert.call_count == 1
    call_args = mock_notifier.send_change_alert.call_args[1]
    assert call_args["url"] == "https://site1.com"
    assert call_args["site_name"] == "Site One"
    assert "Site 1 MODIFIED content!" in call_args["diff_text"]


def test_config_get_sites_from_target_urls_and_json(temp_config):
    # Test comma-separated TARGET_URLS
    temp_config.target_urls_raw = "https://alpha.com, https://beta.com, https://gamma.com"
    temp_config.sites_file_path = "non_existent.json"
    sites = temp_config.get_sites()
    assert len(sites) == 3
    assert [s.url for s in sites] == ["https://alpha.com", "https://beta.com", "https://gamma.com"]

    # Test loading from sites JSON file
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump([
            {"url": "https://custom.com", "name": "Custom Portal", "selector": "#news"}
        ], f)
        json_path = f.name

    try:
        temp_config.sites = []
        temp_config.sites_file_path = json_path
        loaded_sites = temp_config.get_sites()
        assert len(loaded_sites) == 1
        assert loaded_sites[0].url == "https://custom.com"
        assert loaded_sites[0].name == "Custom Portal"
        assert loaded_sites[0].selector == "#news"
    finally:
        if os.path.exists(json_path):
            os.remove(json_path)
