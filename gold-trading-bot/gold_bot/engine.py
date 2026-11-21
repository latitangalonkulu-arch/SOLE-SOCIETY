"""Main polling loop: fetch bars -> strategy signal -> pre-trade filter ->
risk check -> broker order -> journal + push notification. Runs forever
until interrupted.
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
from gold_bot.pretrade_filter import PreTradeFilter
from gold_bot.risk import RiskManager
from gold_bot.strategy import Action, EmaAtrStrategy

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
        self.strategy = EmaAtrStrategy(cfg.strategy)
        self.risk = RiskManager(cfg.risk)
        self.pretrade_filter = PreTradeFilter(cfg.pretrade_filter) if cfg.pretrade_filter.enabled else None

    def run_forever(self) -> None:
        self.notifier.send(
            "Gold bot started",
            f"Symbol: {self.cfg.symbol.display_name} | Broker: {self.cfg.broker.backend} | "
            f"Poll: {self.cfg.engine.poll_interval_seconds}s | "
            f"Pre-trade filter: {'on' if self.pretrade_filter else 'off'}",
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
            # Exits are never gated by the pre-trade filter — only entries are.
            trade = self.broker.close_position(signal.price, signal.reason)
            if trade:
                self.journal.record(trade)
                self._notify_closed(trade)
            return

        if signal.action in (Action.ENTER_LONG, Action.ENTER_SHORT):
            self._try_enter(signal, df)

    def _try_enter(self, signal, df) -> None:
        side = "long" if signal.action == Action.ENTER_LONG else "short"

        if side == "short" and not self.broker.supports_short:
            logger.info("Short signal skipped: %s does not support shorting", type(self.broker).__name__)
            return

        if self.pretrade_filter is not None:
            higher_df = self.feed.get_bars(
                max(self.cfg.engine.lookback_bars, self.pretrade_filter.min_higher_tf_bars_required()),
                self.cfg.pretrade_filter.higher_timeframe,
            )
            result = self.pretrade_filter.evaluate(df, higher_df, side)
            if not result.passed:
                reasons = "; ".join(result.reasons())
                logger.info("Entry signal rejected by pre-trade filter: %s", reasons)
                self.notifier.send(
                    f"Signal skipped ({side}) {self.cfg.symbol.display_name}",
                    f"Pre-trade filter failed:\n{reasons}",
                )
                return

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
        self.notifier.send(
            f"Closed {trade.side.upper()} {self.cfg.symbol.display_name} ({'WIN' if trade.pnl > 0 else 'LOSS'})",
            f"Entry: {trade.entry_price:.2f} -> Exit: {trade.exit_price:.2f}\n"
            f"P&L: {trade.pnl:+.2f}\nReason: {trade.reason}",
            priority="high",
        )


def build_engine(cfg: AppConfig, project_root: Path) -> TradingEngine:
    from gold_bot.data_feed import CCXTFeed
    from gold_bot.notifier import build_notifiers

    feed = CCXTFeed(cfg.symbol.exchange_id, cfg.symbol.symbol)

    if cfg.broker.backend == "ccxt":
        from gold_bot.broker.ccxt_broker import CCXTBroker

        broker = CCXTBroker(
            cfg.symbol.exchange_id, cfg.symbol.symbol,
            project_root / "data" / "ccxt_state.json",
            api_key=cfg.broker.ccxt_api_key, api_secret=cfg.broker.ccxt_api_secret,
            api_password=cfg.broker.ccxt_api_password,
        )
    elif cfg.broker.backend == "paper":
        from gold_bot.broker.paper import PaperBroker

        broker = PaperBroker(cfg.broker.paper_starting_balance, project_root / "data" / "paper_state.json")
    else:
        raise RuntimeError(f"Unknown BROKER backend: {cfg.broker.backend}")

    notifier = FanoutNotifier(build_notifiers(cfg.notifier))
    journal = TradeJournal(project_root / "data" / "trades.csv")

    return TradingEngine(cfg, feed, broker, notifier, journal)
