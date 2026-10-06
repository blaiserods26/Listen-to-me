import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from config import Config

logger = logging.getLogger("WebListener.Notifier")


class EmailNotifier:
    def __init__(self, config: Config):
        self.config = config

    def is_configured(self) -> bool:
        """Check if minimum required SMTP settings are present."""
        return bool(
            self.config.smtp_server
            and self.config.smtp_username
            and self.config.smtp_password
            and self.config.email_recipient
        )

    def send_change_alert(
        self,
        url: str,
        old_hash: str,
        new_hash: str,
        diff_text: Optional[str] = None,
        site_name: Optional[str] = None,
    ) -> bool:
        """Send an email alert informing the user that a website content changed."""
        if not self.is_configured():
            logger.warning(
                "SMTP configuration is incomplete. Skipping email dispatch. "
                "Please configure SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD, and EMAIL_RECIPIENT."
            )
            return False

        display_title = f"{site_name} ({url})" if site_name else url
        subject = f"{self.config.email_subject_prefix} Change Detected on {display_title}"

        # Plain text version
        plain_body = [
            f"Website Change Detected!",
            f"",
            f"Website: {site_name}" if site_name else "",
            f"URL: {url}",
            f"Old Hash (SHA-256): {old_hash}",
            f"New Hash (SHA-256): {new_hash}",
            f"",
        ]
        plain_body = [line for line in plain_body if line != ""]
        if diff_text:
            plain_body.extend([
                "Content Diff Summary:",
                "-" * 40,
                diff_text,
                "-" * 40,
            ])
        plain_body.append("\nThis is an automated notification from your Web-Listener.")
        plain_content = "\n".join(plain_body)

        # HTML formatted version
        diff_html = ""
        if diff_text:
            escaped_diff = html.escape(diff_text)
            diff_lines = []
            for line in escaped_diff.splitlines():
                if line.startswith("+"):
                    diff_lines.append(f'<span style="color: #16a34a; background-color: #dcfce7; display: block;">{line}</span>')
                elif line.startswith("-"):
                    diff_lines.append(f'<span style="color: #dc2626; background-color: #fee2e2; display: block;">{line}</span>')
                elif line.startswith("@"):
                    diff_lines.append(f'<span style="color: #2563eb; background-color: #eff6ff; display: block;">{line}</span>')
                else:
                    diff_lines.append(f'<span>{line}</span><br>')
            diff_html = f"""
            <div style="margin-top: 15px;">
                <h3 style="margin-bottom: 8px; color: #1e293b;">Detected Content Diff:</h3>
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 13px; max-height: 400px; overflow-y: auto; white-space: pre-wrap; line-height: 1.4;">
                    {"".join(diff_lines)}
                </div>
            </div>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; padding: 20px; }}
                .card {{ background: #ffffff; border-radius: 8px; padding: 24px; max-width: 650px; margin: 0 auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border-top: 4px solid #3b82f6; }}
                .tag {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
                .tag-alert {{ background: #fee2e2; color: #dc2626; }}
                .hash-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; font-family: monospace; font-size: 12px; word-break: break-all; margin: 4px 0 12px; }}
                a.btn {{ display: inline-block; background: #2563eb; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 6px; font-weight: 500; margin-top: 16px; }}
            </style>
        </head>
        <body>
            <div class="card">
                <span class="tag tag-alert">Webpage Changed</span>
                <h2 style="color: #0f172a; margin-top: 10px;">Change Detected on Monitored Page</h2>
                <p style="color: #475569; margin-bottom: 16px;">
                    The Web-Listener detected a content hash change for the following address:
                </p>
                <p><strong>Target URL:</strong> <a href="{html.escape(url)}" target="_blank" style="color: #2563eb;">{html.escape(url)}</a></p>
                {f'<p><strong>Site:</strong> {html.escape(site_name)}</p>' if site_name else ''}
                
                <div><strong>Previous Hash:</strong></div>
                <div class="hash-box">{html.escape(old_hash)}</div>

                <div><strong>New Hash:</strong></div>
                <div class="hash-box" style="border-color: #93c5fd; background-color: #eff6ff;">{html.escape(new_hash)}</div>

                {diff_html}

                <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8;">
                    Monitored by Web-Listener Service
                </div>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.email_sender
        msg["To"] = self.config.email_recipient

        part1 = MIMEText(plain_content, "plain", "utf-8")
        part2 = MIMEText(html_content, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)

        try:
            if self.config.smtp_use_ssl:
                server = smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port, timeout=15)

            if self.config.smtp_use_tls and not self.config.smtp_use_ssl:
                server.starttls()

            if self.config.smtp_username and self.config.smtp_password:
                server.login(self.config.smtp_username, self.config.smtp_password)

            server.sendmail(self.config.email_sender, [self.config.email_recipient], msg.as_string())
            server.quit()
            logger.info("Notification email successfully sent to %s", self.config.email_recipient)
            return True
        except Exception as e:
            logger.error("Failed to send notification email: %s", e)
            return False
