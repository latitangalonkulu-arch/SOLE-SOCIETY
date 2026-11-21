"""Shared JSON (de)serialization for a single open Position, used by any
broker that must track SL/TP client-side (PaperBroker, CCXTBroker) since
neither a simulated account nor a typical spot exchange order natively
stores "this fill plus its stop-loss/take-profit" as one object.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from gold_bot.broker.base import Position


def position_to_dict(position: Position | None) -> dict | None:
    if position is None:
        return None
    d = asdict(position)
    d["opened_at"] = position.opened_at.isoformat()
    return d


def position_from_dict(d: dict | None) -> Position | None:
    if d is None:
        return None
    d = dict(d)
    d["opened_at"] = datetime.fromisoformat(d["opened_at"])
    return Position(**d)
