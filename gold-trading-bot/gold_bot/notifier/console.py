import logging

from gold_bot.notifier.base import Notifier

logger = logging.getLogger(__name__)


class ConsoleNotifier(Notifier):
    """Fallback notifier: just logs. Used when no NTFY_TOPIC/Telegram config is set."""

    def send(self, title: str, message: str, priority: str = "default") -> None:
        logger.info("[%s] %s: %s", priority, title, message)
