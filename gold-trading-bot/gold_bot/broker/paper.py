"""Simulated broker for paper trading: no real orders, just bookkeeping
against a virtual balance, persisted to a JSON file so state survives
restarts.

Long/flat only, mirroring CCXTBroker's spot constraint — paper trading is
meant to validate exactly what live trading will actually be able to do.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from gold_bot.broker.base import Broker, ClosedTrade, Position
from gold_bot.broker.state import position_from_dict, position_to_dict


class PaperBroker(Broker):
    supports_short = False

    def __init__(self, starting_balance: float, state_path: Path):
        self.state_path = state_path
        self._balance = starting_balance
        self._position: Position | None = None
        self._load()

    # --- persistence -----------------------------------------------------
    def _load(self) -> None:
        if not self.state_path.exists():
            return
        data = json.loads(self.state_path.read_text())
        self._balance = data["balance"]
        self._position = position_from_dict(data.get("position"))

    def _save(self) -> None:
        data = {
            "balance": self._balance,
            "position": position_to_dict(self._position),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(data, indent=2))

    # --- Broker interface --------------------------------------------------
    def get_equity(self) -> float:
        if self._position is None:
            return self._balance
        # Mark-to-market would need the current price; equity between polls
        # is treated as realized balance only, which is conservative for
        # sizing/kill-switch purposes.
        return self._balance

    def get_open_position(self) -> Position | None:
        return self._position

    def open_position(self, side, units, price, stop_loss, take_profit) -> Position:
        if side == "short":
            raise ValueError(f"{self.__class__.__name__} is long-only and cannot open a short position")
        if self._position is not None:
            raise RuntimeError("Position already open; close it before opening a new one")
        self._position = Position(
            side=side, units=units, entry_price=price,
            stop_loss=stop_loss, take_profit=take_profit,
            opened_at=datetime.now(timezone.utc),
        )
        self._save()
        return self._position

    def close_position(self, price: float, reason: str) -> ClosedTrade | None:
        if self._position is None:
            return None
        pos = self._position
        pnl = (price - pos.entry_price) * pos.units
        self._balance += pnl
        trade = ClosedTrade(
            side=pos.side, units=pos.units, entry_price=pos.entry_price,
            exit_price=price, opened_at=pos.opened_at,
            closed_at=datetime.now(timezone.utc), pnl=pnl, reason=reason,
        )
        self._position = None
        self._save()
        return trade

    def check_stop_take(self, current_price: float) -> ClosedTrade | None:
        pos = self._position
        if pos is None:
            return None
        if pos.stop_loss is not None and current_price <= pos.stop_loss:
            return self.close_position(pos.stop_loss, "stop_loss hit")
        if pos.take_profit is not None and current_price >= pos.take_profit:
            return self.close_position(pos.take_profit, "take_profit hit")
        return None
