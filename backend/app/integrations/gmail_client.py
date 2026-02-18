from __future__ import annotations

import asyncio
import base64
import logging
import os
from email.mime.text import MIMEText
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _get_gmail_service():
    """Build the Gmail API service using stored OAuth credentials."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    token_path = settings.gmail_token_path
    creds_path = settings.gmail_credentials_path

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    f"Gmail credentials not found at {creds_path}. "
                    "Download from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


class GmailClient:
    def __init__(self) -> None:
        self._service = None
        self._last_history_id: str | None = None

    @property
    def service(self):
        if self._service is None:
            self._service = _get_gmail_service()
        return self._service

    def is_configured(self) -> bool:
        return os.path.exists(settings.gmail_credentials_path)

    def fetch_recent_emails(self, max_results: int = 10) -> list[dict[str, Any]]:
        """Fetch recent unread emails."""
        try:
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q="is:unread", maxResults=max_results)
                .execute()
            )
            messages = results.get("messages", [])
            emails = []
            for msg_ref in messages:
                msg = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=msg_ref["id"], format="full")
                    .execute()
                )
                emails.append(self._parse_email(msg))
            return emails
        except Exception as e:
            logger.error("Failed to fetch emails: %s", e)
            return []

    def _parse_email(self, msg: dict) -> dict[str, Any]:
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        body = ""
        payload = msg.get("payload", {})

        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                        break
        elif "body" in payload:
            data = payload["body"].get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        return {
            "id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "sender": headers.get("from", ""),
            "subject": headers.get("subject", ""),
            "body": body[:2000],
            "date": headers.get("date", ""),
            "snippet": msg.get("snippet", ""),
        }

    def send_reply(self, thread_id: str, to: str, subject: str, body: str) -> dict:
        """Send a reply email."""
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        try:
            result = (
                self.service.users()
                .messages()
                .send(userId="me", body={"raw": raw, "threadId": thread_id})
                .execute()
            )
            logger.info("Sent reply to %s (thread: %s)", to, thread_id)
            return result
        except Exception as e:
            logger.error("Failed to send reply: %s", e)
            raise

    def mark_as_read(self, message_id: str) -> None:
        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
        except Exception as e:
            logger.error("Failed to mark as read: %s", e)


gmail_client = GmailClient()
