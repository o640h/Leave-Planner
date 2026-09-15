"""Provider-neutral transactional email delivery with a safe local outbox."""

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from settings import Settings


@dataclass(frozen=True)
class EmailMessage:
    recipient: str
    subject: str
    text: str


@dataclass(frozen=True)
class OutboxMessage:
    id: str
    idempotency_key: str
    recipient: str
    subject: str
    text: str


class EmailDeliveryError(Exception):
    """A redacted provider failure safe to record without response content."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class EmailSender(Protocol):
    def send(self, message: EmailMessage, *, idempotency_key: str) -> str: ...


class DevelopmentOutbox:
    """Capture messages in memory so development never sends external email."""

    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    def send(self, message: EmailMessage, *, idempotency_key: str) -> str:
        message_id = f"development-{len(self.messages) + 1}"
        self.messages.append(
            OutboxMessage(
                id=message_id,
                idempotency_key=idempotency_key,
                recipient=message.recipient,
                subject=message.subject,
                text=message.text,
            )
        )
        return message_id


class ResendEmailSender:
    """Send one plain-text transactional message through Resend's HTTPS API."""

    endpoint = "https://api.resend.com/emails"

    def __init__(self, *, api_key: str, sender: str, reply_to: str | None = None) -> None:
        self.api_key = api_key
        self.sender = sender
        self.reply_to = reply_to

    def send(self, message: EmailMessage, *, idempotency_key: str) -> str:
        payload: dict[str, object] = {
            "from": self.sender,
            "to": [message.recipient],
            "subject": message.subject,
            "text": message.text,
        }
        if self.reply_to:
            payload["reply_to"] = self.reply_to
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
                "User-Agent": "Leave-Planner/0.2",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise EmailDeliveryError(f"provider_http_{error.code}") from error
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise EmailDeliveryError("provider_unavailable") from error
        message_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(message_id, str) or not message_id:
            raise EmailDeliveryError("provider_invalid_response")
        return message_id


def create_email_sender(settings: Settings) -> EmailSender:
    if settings.environment == "production" and settings.email_provider != "resend":
        raise RuntimeError("Production requires the Resend email provider")
    if settings.email_provider == "development_outbox":
        return DevelopmentOutbox()
    return ResendEmailSender(
        api_key=settings.resend_api_key,
        sender=settings.email_from,
        reply_to=settings.email_reply_to,
    )
