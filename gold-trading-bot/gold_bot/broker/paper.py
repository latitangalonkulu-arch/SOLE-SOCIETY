"""Simulated broker for paper trading: no real orders, just bookkeeping
against a virtual balance, persisted to a JSON file so state survives
restarts.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from gold_bot.broker.base import Broker, ClosedTrade, Position


class PaperBroker(Broker):
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
        pos = data.get("position")
        if pos:
            pos["opened_at"] = datetime.fromisoformat(pos["opened_at"])
            self._position = Position(**pos)

    def _save(self) -> None:
        data = {
            "balance": self._balance,
            "position": None,
        }
        if self._position:
            p = asdict(self._position)
            p["opened_at"] = self._position.opened_at.isoformat()
            data["position"] = p
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
        pnl = self._calc_pnl(pos, price)
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
        if pos.side == "long":
            if pos.stop_loss is not None and current_price <= pos.stop_loss:
                return self.close_position(pos.stop_loss, "stop_loss hit")
            if pos.take_profit is not None and current_price >= pos.take_profit:
                return self.close_position(pos.take_profit, "take_profit hit")
        else:
            if pos.stop_loss is not None and current_price >= pos.stop_loss:
                return self.close_position(pos.stop_loss, "stop_loss hit")
            if pos.take_profit is not None and current_price <= pos.take_profit:
                return self.close_position(pos.take_profit, "take_profit hit")
        return None

    @staticmethod
    def _calc_pnl(pos: Position, exit_price: float) -> float:
        if pos.side == "long":
            return (exit_price - pos.entry_price) * pos.units
        return (pos.entry_price - exit_price) * pos.units
