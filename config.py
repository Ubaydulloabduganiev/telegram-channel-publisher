from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_admin_ids(raw: str) -> frozenset[int]:
    values: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.add(int(part))
        except ValueError as exc:
            raise RuntimeError(f"Invalid Telegram user ID in ADMIN_IDS: {part}") from exc
    if not values:
        raise RuntimeError("ADMIN_IDS must contain at least one Telegram user ID.")
    return frozenset(values)


def parse_chat_id(raw: str) -> int | str:
    raw = raw.strip()
    if raw.startswith("@"):
        return raw
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(
            "CHANNEL_ID must be @channel_username or a numeric Telegram chat ID."
        ) from exc


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    channel_id: int | str
    admin_ids: frozenset[int]
    base_url: str
    webhook_path: str
    webhook_secret: str
    port: int

    @property
    def webhook_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.webhook_path}"


def load_config() -> Config:
    token = required("BOT_TOKEN")

    # Render sets this automatically for Web Services.
    base_url = (
        os.getenv("RENDER_EXTERNAL_URL", "").strip()
        or os.getenv("PUBLIC_BASE_URL", "").strip()
    )
    if not base_url:
        raise RuntimeError(
            "No public URL found. On Render, RENDER_EXTERNAL_URL is automatic. "
            "For local webhook testing, set PUBLIC_BASE_URL."
        )

    # Telegram webhook secret tokens allow A-Z, a-z, 0-9, _ and -.
    # A SHA-256 hex digest is valid and avoids another secret the user must configure.
    webhook_secret = hashlib.sha256(token.encode("utf-8")).hexdigest()

    return Config(
        bot_token=token,
        channel_id=parse_chat_id(required("CHANNEL_ID")),
        admin_ids=parse_admin_ids(required("ADMIN_IDS")),
        base_url=base_url,
        webhook_path="/telegram/webhook",
        webhook_secret=webhook_secret,
        port=int(os.getenv("PORT", "10000")),
    )
