"""Entry/exit signal generation: EMA trend crossover, filtered by RSI,
with ATR-based stop-loss / take-profit distances.

Indicators are implemented directly on pandas (no TA-Lib dependency, which
is awkward to install on a phone-adjacent/cloud box).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from gold_bot.config import StrategyConfig


class Action(Enum):
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT = "exit"
    HOLD = "hold"


@dataclass(frozen=True)
class Signal:
    action: Action
    price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str = ""


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


class EmaRsiAtrStrategy:
    """Long when fast EMA crosses above slow EMA and RSI isn't overbought.
    Short when fast EMA crosses below slow EMA and RSI isn't oversold.
    Exit an open position on the opposite crossover (SL/TP are enforced by
    the broker/engine between polls, not by this function).
    """

    def __init__(self, cfg: StrategyConfig):
        self.cfg = cfg

    def min_bars_required(self) -> int:
        return max(self.cfg.slow_ema, self.cfg.rsi_period, self.cfg.atr_period) + 2

    def generate_signal(self, df: pd.DataFrame, current_side: str | None) -> Signal:
        """`current_side` is "long", "short", or None for flat."""
        c = self.cfg
        if len(df) < self.min_bars_required():
            return Signal(Action.HOLD, price=float(df["close"].iloc[-1]), reason="not enough history")

        fast = ema(df["close"], c.fast_ema)
        slow = ema(df["close"], c.slow_ema)
        rsi_vals = rsi(df["close"], c.rsi_period)
        atr_vals = atr(df, c.atr_period)

        price = float(df["close"].iloc[-1])
        fast_now, fast_prev = fast.iloc[-1], fast.iloc[-2]
        slow_now, slow_prev = slow.iloc[-1], slow.iloc[-2]
        rsi_now = rsi_vals.iloc[-1]
        atr_now = atr_vals.iloc[-1]

        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now

        if current_side == "long" and crossed_down:
            return Signal(Action.EXIT, price=price, reason="EMA crossed down, exiting long")
        if current_side == "short" and crossed_up:
            return Signal(Action.EXIT, price=price, reason="EMA crossed up, exiting short")

        if current_side is None:
            if crossed_up and rsi_now < c.rsi_overbought:
                sl = price - atr_now * c.stop_loss_atr_mult
                tp = price + atr_now * c.take_profit_atr_mult
                return Signal(Action.ENTER_LONG, price=price, stop_loss=sl, take_profit=tp,
                              reason=f"EMA({c.fast_ema}) crossed above EMA({c.slow_ema}), RSI={rsi_now:.1f}")
            if crossed_down and rsi_now > c.rsi_oversold:
                sl = price + atr_now * c.stop_loss_atr_mult
                tp = price - atr_now * c.take_profit_atr_mult
                return Signal(Action.ENTER_SHORT, price=price, stop_loss=sl, take_profit=tp,
                              reason=f"EMA({c.fast_ema}) crossed below EMA({c.slow_ema}), RSI={rsi_now:.1f}")

        return Signal(Action.HOLD, price=price, reason="no new signal")
