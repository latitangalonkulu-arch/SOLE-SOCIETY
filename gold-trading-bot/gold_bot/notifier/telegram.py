from __future__ import annotations

import logging

import requests

from gold_bot.notifier.base import Notifier

logger = logging.getLogger(__name__)


class TelegramNotifier(Notifier):
    def __init__(self, bot_token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id

    def send(self, title: str, message: str, priority: str = "default") -> None:
        try:
            requests.post(
                self.url,
                json={"chat_id": self.chat_id, "text": f"*{title}*\n{message}", "parse_mode": "Markdown"},
                timeout=10,
            )
        except requests.RequestException:
            logger.exception("Failed to send Telegram notification")
