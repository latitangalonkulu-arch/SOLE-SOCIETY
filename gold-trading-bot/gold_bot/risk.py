"""Position sizing and a daily-loss kill switch.

Risk is defined in account-currency terms: risking `risk_per_trade` fraction
of current equity on the distance between entry and stop-loss.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from gold_bot.config import RiskConfig


@dataclass
class SizingResult:
    allowed: bool
    units: float = 0.0
    reason: str = ""


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg
        self._day: date | None = None
        self._equity_at_day_start: float = 0.0

    def _roll_day_if_needed(self, equity: float) -> None:
        today = date.today()
        if self._day != today:
            self._day = today
            self._equity_at_day_start = equity

    def daily_loss_limit_hit(self, equity: float) -> bool:
        self._roll_day_if_needed(equity)
        if self._equity_at_day_start <= 0:
            return False
        drawdown = (self._equity_at_day_start - equity) / self._equity_at_day_start
        return drawdown >= self.cfg.max_daily_loss_pct

    def size_position(
        self, equity: float, entry_price: float, stop_loss: float, open_position_count: int
    ) -> SizingResult:
        self._roll_day_if_needed(equity)

        if open_position_count >= self.cfg.max_open_positions:
            return SizingResult(False, reason="max_open_positions reached")

        if self.daily_loss_limit_hit(equity):
            return SizingResult(False, reason="daily loss limit reached, no new trades today")

        stop_distance = abs(entry_price - stop_loss)
        if stop_distance <= 0:
            return SizingResult(False, reason="invalid stop distance")

        risk_amount = equity * self.cfg.risk_per_trade
        units = risk_amount / stop_distance
        if units <= 0:
            return SizingResult(False, reason="computed size is zero")

        return SizingResult(True, units=units, reason="ok")
