"""Append-only CSV trade log + simple summary stats, so you can review
performance from your phone (open the CSV in any spreadsheet/file app)
before trusting the bot with more risk or real money.
"""
from __future__ import annotations

import csv
from pathlib import Path

from gold_bot.broker.base import ClosedTrade

_FIELDS = ["opened_at", "closed_at", "side", "units", "entry_price", "exit_price", "pnl", "reason"]


class TradeJournal:
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        if not self.csv_path.exists():
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=_FIELDS).writeheader()

    def record(self, trade: ClosedTrade) -> None:
        with open(self.csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDS)
            writer.writerow({
                "opened_at": trade.opened_at.isoformat(),
                "closed_at": trade.closed_at.isoformat(),
                "side": trade.side,
                "units": trade.units,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "pnl": round(trade.pnl, 2),
                "reason": trade.reason,
            })

    def summary(self) -> dict:
        rows = list(csv.DictReader(open(self.csv_path))) if self.csv_path.exists() else []
        if not rows:
            return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "total_pnl": 0.0}
        pnls = [float(r["pnl"]) for r in rows]
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p <= 0)
        return {
            "trades": len(rows),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / len(rows), 3),
            "total_pnl": round(sum(pnls), 2),
        }
