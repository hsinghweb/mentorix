from __future__ import annotations

import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.core.settings import settings


class EmailService:
    def __init__(self) -> None:
        self.host = settings.email_host
        self.port = int(settings.email_port or 587)
        self.user = settings.email_user
        self.password = settings.email_pass
        self.sender = settings.email_from or self.user
        self.gmail_api_credentials_json = settings.gmail_api_credentials_json

    def _build_html(self, *, learner_name: str, week_label: str, progress_percentage: float, reason: str) -> str:
        return (
            "<html><body>"
            f"<h3>Mentorix Weekly Reminder</h3>"
            f"<p>Hi {learner_name},</p>"
            f"<p>Your plan for <b>{week_label}</b> is still in progress.</p>"
            f"<p>Progress: <b>{round(progress_percentage, 1)}%</b></p>"
            f"<p>Reason: {reason.replace('_', ' ')}</p>"
            "<p>Log in to continue your study plan.</p>"
            "</body></html>"
        )

    def _send_smtp(self, *, recipient: str, subject: str, html: str) -> None:
        if not (self.host and self.user and self.password and self.sender):
            raise RuntimeError("SMTP configuration is incomplete.")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = recipient
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(self.host, self.port, timeout=20) as server:
            server.starttls()
            server.login(self.user, self.password)
            server.sendmail(self.sender, [recipient], msg.as_string())

    def _send_gmail_api_stub(self, *, recipient: str, subject: str, html: str) -> None:
        # Placeholder hook: parse credentials and fail clearly if not configured end-to-end.
        if not self.gmail_api_credentials_json:
            raise RuntimeError("Gmail API credentials not configured.")
        _ = json.loads(self.gmail_api_credentials_json)
        raise RuntimeError("Gmail API send flow is not configured in this environment.")

    def send_reminder(
        self,
        *,
        recipient: str,
        learner_name: str,
        week_label: str,
        progress_percentage: float,
        reason: str,
        mode: str = "smtp",
    ) -> dict[str, Any]:
        subject = f"Mentorix Reminder: {week_label}"
        html = self._build_html(
            learner_name=learner_name,
            week_label=week_label,
            progress_percentage=progress_percentage,
            reason=reason,
        )
        if mode == "gmail_api":
            self._send_gmail_api_stub(recipient=recipient, subject=subject, html=html)
        else:
            self._send_smtp(recipient=recipient, subject=subject, html=html)
        return {
            "recipient": recipient,
            "subject": subject,
            "mode": mode,
            "html_size": len(html),
        }

    def diagnostics(self) -> dict[str, Any]:
        smtp_missing = []
        if not self.host:
            smtp_missing.append("EMAIL_HOST")
        if not self.user:
            smtp_missing.append("EMAIL_USER")
        if not self.password:
            smtp_missing.append("EMAIL_PASS")
        if not self.sender:
            smtp_missing.append("EMAIL_FROM")

        gmail_ready = False
        gmail_error = None
        if self.gmail_api_credentials_json:
            try:
                parsed = json.loads(self.gmail_api_credentials_json)
                gmail_ready = isinstance(parsed, dict) and bool(parsed)
            except Exception as exc:
                gmail_error = str(exc)

        return {
            "smtp": {
                "ready": len(smtp_missing) == 0,
                "host": self.host or None,
                "port": self.port,
                "from": self.sender or None,
                "missing": smtp_missing,
            },
            "gmail_api": {
                "ready": gmail_ready,
                "configured": bool(self.gmail_api_credentials_json),
                "error": gmail_error,
            },
        }


email_service = EmailService()

