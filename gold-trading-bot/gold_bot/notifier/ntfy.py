"""Push notifications via ntfy.sh — free, no account needed. Install the
ntfy app (Android/iOS) and subscribe to your topic to get entry/exit
alerts on your phone.
"""
from __future__ import annotations

import logging

import requests

from gold_bot.notifier.base import Notifier

logger = logging.getLogger(__name__)

_PRIORITY_MAP = {"default": "3", "high": "4", "urgent": "5", "low": "2"}


class NtfyNotifier(Notifier):
    def __init__(self, topic: str, server: str = "https://ntfy.sh"):
        self.url = f"{server.rstrip('/')}/{topic}"

    def send(self, title: str, message: str, priority: str = "default") -> None:
        try:
            requests.post(
                self.url,
                data=message.encode("utf-8"),
                headers={
                    "Title": title,
                    "Priority": _PRIORITY_MAP.get(priority, "3"),
                    "Tags": "moneybag",
                },
                timeout=10,
            )
        except requests.RequestException:
            logger.exception("Failed to send ntfy notification")
