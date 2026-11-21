from gold_bot.config import NotifierConfig
from gold_bot.notifier.base import Notifier
from gold_bot.notifier.console import ConsoleNotifier
from gold_bot.notifier.ntfy import NtfyNotifier
from gold_bot.notifier.telegram import TelegramNotifier


def build_notifiers(cfg: NotifierConfig) -> list[Notifier]:
    """Builds every notifier that has credentials configured. Falls back to
    console logging if none are configured, so the bot never fails silently.
    """
    notifiers: list[Notifier] = []
    if cfg.ntfy_topic:
        notifiers.append(NtfyNotifier(cfg.ntfy_topic, cfg.ntfy_server))
    if cfg.telegram_bot_token and cfg.telegram_chat_id:
        notifiers.append(TelegramNotifier(cfg.telegram_bot_token, cfg.telegram_chat_id))
    if not notifiers:
        notifiers.append(ConsoleNotifier())
    return notifiers


class FanoutNotifier(Notifier):
    """Sends to every configured backend; one failing doesn't block the others."""

    def __init__(self, notifiers: list[Notifier]):
        self.notifiers = notifiers

    def send(self, title: str, message: str, priority: str = "default") -> None:
        for n in self.notifiers:
            n.send(title, message, priority)
