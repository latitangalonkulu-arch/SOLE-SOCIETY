"""Real broker adapter for MetaTrader 5.

IMPORTANT: this only works when the process runs on the same machine as a
MetaTrader 5 terminal that is installed, running, and logged into your
broker account (Windows, or a Windows VPS — the MetaTrader5 Python package
talks to the local terminal process, it is not a remote API). It cannot
run inside this cloud container. Install with `pip install MetaTrader5`
on that machine, set BROKER=mt5 and the MT5_* variables in .env, then run
the bot there.

Unlike the paper broker, MT5 enforces stop-loss/take-profit on the broker
server itself (attached to the order), so check_stop_take() here just
detects that the position MT5 was tracking is no longer open and reports
it as closed — it does not need to compute the exit price itself.
"""
from __future__ import annotations

from datetime import datetime, timezone

from gold_bot.broker.base import Broker, ClosedTrade, Position


class MT5Broker(Broker):
    def __init__(self, login: int, password: str, server: str, symbol: str):
        try:
            import MetaTrader5 as mt5  # noqa: N814
        except ImportError as e:
            raise RuntimeError(
                "MetaTrader5 package not installed. This broker only runs on "
                "the Windows machine/VPS with a logged-in MT5 terminal."
            ) from e
        self._mt5 = mt5
        self.symbol = symbol

        if not mt5.initialize(login=login, password=password, server=server):
            raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")

        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"MT5 could not select symbol {symbol}: {mt5.last_error()}")

        self._tracked_ticket: int | None = None
        self._tracked_opened_at: datetime | None = None

    def get_equity(self) -> float:
        info = self._mt5.account_info()
        if info is None:
            raise RuntimeError(f"MT5 account_info() failed: {self._mt5.last_error()}")
        return float(info.equity)

    def get_open_position(self) -> Position | None:
        positions = self._mt5.positions_get(symbol=self.symbol)
        if not positions:
            self._tracked_ticket = None
            return None
        p = positions[0]
        self._tracked_ticket = p.ticket
        side = "long" if p.type == self._mt5.ORDER_TYPE_BUY else "short"
        opened_at = datetime.fromtimestamp(p.time, tz=timezone.utc)
        self._tracked_opened_at = opened_at
        return Position(
            side=side, units=p.volume, entry_price=p.price_open,
            stop_loss=p.sl or None, take_profit=p.tp or None, opened_at=opened_at,
        )

    def open_position(self, side, units, price, stop_loss, take_profit) -> Position:
        order_type = self._mt5.ORDER_TYPE_BUY if side == "long" else self._mt5.ORDER_TYPE_SELL
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": round(units, 2),
            "type": order_type,
            "sl": stop_loss or 0.0,
            "tp": take_profit or 0.0,
            "deviation": 20,
            "magic": 20260101,
            "comment": "gold_bot entry",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }
        result = self._mt5.order_send(request)
        if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 order_send failed: {result}")
        opened_at = datetime.now(timezone.utc)
        self._tracked_ticket = result.order
        self._tracked_opened_at = opened_at
        return Position(
            side=side, units=units, entry_price=result.price,
            stop_loss=stop_loss, take_profit=take_profit, opened_at=opened_at,
        )

    def close_position(self, price: float, reason: str) -> ClosedTrade | None:
        positions = self._mt5.positions_get(symbol=self.symbol)
        if not positions:
            return None
        p = positions[0]
        close_type = self._mt5.ORDER_TYPE_SELL if p.type == self._mt5.ORDER_TYPE_BUY else self._mt5.ORDER_TYPE_BUY
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": p.volume,
            "type": close_type,
            "position": p.ticket,
            "deviation": 20,
            "magic": 20260101,
            "comment": f"gold_bot exit: {reason}",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }
        result = self._mt5.order_send(request)
        if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 close order_send failed: {result}")

        side = "long" if p.type == self._mt5.ORDER_TYPE_BUY else "short"
        pnl = (result.price - p.price_open) * p.volume if side == "long" else (p.price_open - result.price) * p.volume
        opened_at = self._tracked_opened_at or datetime.fromtimestamp(p.time, tz=timezone.utc)
        self._tracked_ticket = None
        return ClosedTrade(
            side=side, units=p.volume, entry_price=p.price_open, exit_price=result.price,
            opened_at=opened_at, closed_at=datetime.now(timezone.utc), pnl=pnl, reason=reason,
        )

    def check_stop_take(self, current_price: float) -> ClosedTrade | None:
        """MT5 closes SL/TP orders on the server; detect that it happened."""
        if self._tracked_ticket is None:
            return None
        still_open = self._mt5.positions_get(symbol=self.symbol)
        if still_open:
            return None
        # Position we were tracking is gone — pull the closing deal from history.
        deals = self._mt5.history_deals_get(position=self._tracked_ticket)
        ticket = self._tracked_ticket
        self._tracked_ticket = None
        if not deals:
            return None
        closing_deal = deals[-1]
        side = "long" if closing_deal.type == self._mt5.DEAL_TYPE_SELL else "short"
        return ClosedTrade(
            side=side, units=closing_deal.volume, entry_price=0.0,
            exit_price=closing_deal.price, opened_at=self._tracked_opened_at or datetime.now(timezone.utc),
            closed_at=datetime.now(timezone.utc), pnl=closing_deal.profit,
            reason=f"broker-side close (ticket {ticket})",
        )
