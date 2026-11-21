from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    side: str  # "long" | "short"
    units: float
    entry_price: float
    stop_loss: float | None
    take_profit: float | None
    opened_at: datetime


@dataclass
class ClosedTrade:
    side: str
    units: float
    entry_price: float
    exit_price: float
    opened_at: datetime
    closed_at: datetime
    pnl: float
    reason: str


class Broker(ABC):
    @abstractmethod
    def get_equity(self) -> float: ...

    @abstractmethod
    def get_open_position(self) -> Position | None: ...

    @abstractmethod
    def open_position(self, side: str, units: float, price: float,
                       stop_loss: float | None, take_profit: float | None) -> Position: ...

    @abstractmethod
    def close_position(self, price: float, reason: str) -> ClosedTrade | None: ...

    @abstractmethod
    def check_stop_take(self, current_price: float) -> ClosedTrade | None:
        """Called every poll to see if SL/TP was hit since the last check."""
