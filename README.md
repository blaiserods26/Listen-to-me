# Multi-Website Listener 🌐🔔

A robust, configurable website change monitor that tracks one or multiple web pages by calculating cryptographic SHA-256 hashes of their content. When any monitored site changes, it immediately triggers an email alert containing the site name, URL, previous & new hashes, and a formatted unified diff of the update.

---

## ✨ Features

- **Multi-Website Monitoring**: Track multiple websites simultaneously with a single listener instance.
- **SHA-256 Content Hashing**: High-fidelity change detection based on cryptographic hash digests.
- **Smart Noise Filtering**: Strips dynamic `<script>`, `<style>`, `<noscript>`, `<iframe>`, and comments to prevent false alarms from ad trackers, timestamps, and analytics.
- **Targeted Element Monitoring**: Support for CSS selectors (e.g. `#announcements`, `article`, `main`) globally or per-site.
- **Unified Diff Generation**: Highlights added and removed text lines directly in the email notification (rendered with colored diff styling in HTML).
- **Persistent State**: Retains past hashes and content for every website in `state.json` across process restarts.
- **Flexible Execution**:
  - Run as a continuous daemon polling at custom intervals.
  - Run in one-shot mode (`--once`) for integration with Windows Task Scheduler or Linux cron.
  - Built-in `--test-email` diagnostic tool to verify SMTP credentials.

---

## 🚀 Configuration Options

You can configure websites in any of the following 3 ways:

### Method 1: Multiple URLs in `.env` (Quickest)
Edit your `.env` file:
```ini
TARGET_URLS=https://example.com, https://news.ycombinator.com, https://httpbin.org/html
CHECK_INTERVAL_SECONDS=3600

# SMTP Configuration (Example: Gmail)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
EMAIL_SENDER=your_email@gmail.com
EMAIL_RECIPIENT=recipient@example.com
```

### Method 2: Per-Site Custom Settings (`sites.json`)
If you want friendly names or specific CSS selectors per site, create `sites.json`:
```json
[
  {
    "url": "https://example.com",
    "name": "Example Domain",
    "selector": "body"
  },
  {
    "url": "https://news.ycombinator.com",
    "name": "Hacker News Frontpage",
    "selector": "table#hnmain"
  },
  {
    "url": "https://httpbin.org/html",
    "name": "Httpbin HTML Demo"
  }
]
```

### Method 3: Command-Line Flags
Pass URLs on the fly:
```bash
python main.py --urls https://example.com https://news.ycombinator.com
```

---

## 💻 Running the Listener

### Verify Email Setup
```bash
python main.py --test-email
```

### Continuous Daemon Mode
Polls all configured websites at the set interval:
```bash
python main.py
```

### Run Once (Windows Task Scheduler / Cron)
Checks all websites once and terminates:
```bash
python main.py --once
```

---

## 🛠️ CLI Options

| Argument | Description |
| :--- | :--- |
| `--urls <URL1> <URL2> ...` | Monitors one or more space-separated URLs |
| `--url <URL>` | Monitors a single URL |
| `--sites-file <PATH>` | Path to custom `sites.json` config file |
| `--selector <CSS>` | Default CSS selector to watch |
| `--interval <SEC>` | Overrides the polling interval in seconds |
| `--once` | Checks all websites once and exits immediately |
| `--test-email` | Sends a test verification email and exits |

---

## 🧪 Running Tests

Run the test suite using pytest:
```bash
python -m pytest tests/
```

---

## ☁️ Free Cloud Hosting via GitHub Actions

This project can run 100% free without maintaining any server using the included [`.github/workflows/monitor.yml`](.github/workflows/monitor.yml).

### Setup:
1. Push this repository to GitHub (Private or Public).
2. Go to **Settings** → **Secrets and variables** → **Actions** in your GitHub repository.
3. Under **Repository secrets**, add:
   - `SMTP_USERNAME`: Your Gmail or SMTP username.
   - `SMTP_PASSWORD`: Your Gmail App Password (16 characters).
   - `EMAIL_RECIPIENT`: Target recipient email address.
   - `TARGET_URLS`: Comma-separated list of URLs to monitor (e.g. `https://example.com, https://news.ycombinator.com`).
4. Under **Settings** → **Actions** → **General** → **Workflow permissions**, select **Read and write permissions** (this allows the action to commit updated `state.json` back to your repo).
5. The workflow will automatically run every hour via cron, and you can also manually trigger it anytime from the **Actions** tab with "Run workflow".

