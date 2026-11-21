"""Main polling loop: fetch bars -> strategy signal -> risk check -> broker
order -> journal + push notification. Runs forever until interrupted.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from gold_bot.broker.base import Broker
from gold_bot.config import AppConfig
from gold_bot.data_feed import PriceFeed
from gold_bot.journal import TradeJournal
from gold_bot.notifier import FanoutNotifier
from gold_bot.risk import RiskManager
from gold_bot.strategy import Action, EmaRsiAtrStrategy

logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(
        self,
        cfg: AppConfig,
        feed: PriceFeed,
        broker: Broker,
        notifier: FanoutNotifier,
        journal: TradeJournal,
    ):
        self.cfg = cfg
        self.feed = feed
        self.broker = broker
        self.notifier = notifier
        self.journal = journal
        self.strategy = EmaRsiAtrStrategy(cfg.strategy)
        self.risk = RiskManager(cfg.risk)

    def run_forever(self) -> None:
        self.notifier.send(
            "Gold bot started",
            f"Symbol: {self.cfg.symbol.display_name} | Broker: {self.cfg.broker.backend} | "
            f"Poll: {self.cfg.engine.poll_interval_seconds}s",
        )
        while True:
            try:
                self.run_once()
            except Exception as e:  # keep the bot alive across transient data/network errors
                logger.exception("Error during poll cycle")
                self.notifier.send("Gold bot error", str(e), priority="high")
            time.sleep(self.cfg.engine.poll_interval_seconds)

    def run_once(self) -> None:
        df = self.feed.get_bars(self.cfg.engine.lookback_bars, self.cfg.engine.bar_interval)
        current_price = float(df["close"].iloc[-1])

        # 1. Did an open position's stop-loss/take-profit get hit since last poll?
        closed = self.broker.check_stop_take(current_price)
        if closed:
            self.journal.record(closed)
            self._notify_closed(closed)

        position = self.broker.get_open_position()
        current_side = position.side if position else None

        signal = self.strategy.generate_signal(df, current_side)

        if signal.action == Action.EXIT and position is not None:
            trade = self.broker.close_position(signal.price, signal.reason)
            if trade:
                self.journal.record(trade)
                self._notify_closed(trade)
            return

        if signal.action in (Action.ENTER_LONG, Action.ENTER_SHORT):
            side = "long" if signal.action == Action.ENTER_LONG else "short"
            equity = self.broker.get_equity()
            open_count = 1 if self.broker.get_open_position() else 0
            sizing = self.risk.size_position(equity, signal.price, signal.stop_loss, open_count)
            if not sizing.allowed:
                logger.info("Signal %s rejected by risk manager: %s", side, sizing.reason)
                return
            pos = self.broker.open_position(side, sizing.units, signal.price, signal.stop_loss, signal.take_profit)
            self._notify_opened(pos, signal.reason)

    def _notify_opened(self, pos, reason: str) -> None:
        self.notifier.send(
            f"Entered {pos.side.upper()} {self.cfg.symbol.display_name}",
            f"Price: {pos.entry_price:.2f} | SL: {pos.stop_loss:.2f} | TP: {pos.take_profit:.2f}\n"
            f"Units: {pos.units:.4f}\n{reason}",
            priority="high",
        )

    def _notify_closed(self, trade) -> None:
        emoji_reason = trade.reason
        self.notifier.send(
            f"Closed {trade.side.upper()} {self.cfg.symbol.display_name} ({'WIN' if trade.pnl > 0 else 'LOSS'})",
            f"Entry: {trade.entry_price:.2f} -> Exit: {trade.exit_price:.2f}\n"
            f"P&L: {trade.pnl:+.2f}\nReason: {emoji_reason}",
            priority="high",
        )


def build_engine(cfg: AppConfig, project_root: Path) -> TradingEngine:
    from gold_bot.broker.paper import PaperBroker
    from gold_bot.data_feed import YFinanceFeed
    from gold_bot.notifier import build_notifiers

    feed = YFinanceFeed(cfg.symbol.yfinance_ticker)

    if cfg.broker.backend == "mt5":
        from gold_bot.broker.mt5 import MT5Broker
        from gold_bot.data_feed import MT5Feed

        if not all([cfg.broker.mt5_login, cfg.broker.mt5_password, cfg.broker.mt5_server, cfg.broker.mt5_symbol]):
            raise RuntimeError("BROKER=mt5 requires MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_SYMBOL in .env")
        broker = MT5Broker(cfg.broker.mt5_login, cfg.broker.mt5_password, cfg.broker.mt5_server, cfg.broker.mt5_symbol)
        feed = MT5Feed(cfg.broker.mt5_symbol)
    elif cfg.broker.backend == "paper":
        broker = PaperBroker(cfg.broker.paper_starting_balance, project_root / "data" / "paper_state.json")
    else:
        raise RuntimeError(f"Unknown BROKER backend: {cfg.broker.backend}")

    notifier = FanoutNotifier(build_notifiers(cfg.notifier))
    journal = TradeJournal(project_root / "data" / "trades.csv")

    return TradingEngine(cfg, feed, broker, notifier, journal)
