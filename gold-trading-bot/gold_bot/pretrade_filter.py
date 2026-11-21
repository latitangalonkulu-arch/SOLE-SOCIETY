"""Pre-trade confirmation gate.

Before any entry signal is actually placed as an order, the engine runs
this filter. An entry is only allowed through if ALL of these pass:

  1. Trend alignment on a higher timeframe — price must be on the correct
     side of an EMA computed on a higher timeframe than the one the entry
     signal fired on (e.g. entries on 15m bars, trend check on 1h bars).
  2. RSI isn't overbought (for longs) / oversold (for shorts) on the entry
     timeframe.
  3. Volume spike — the current bar's volume must exceed its recent
     rolling average by a configurable multiplier, as a sign of real
     participation behind the move rather than a thin/low-conviction tick.

This is intentionally independent of gold_bot/strategy.py so you can tune
these thresholds against your paper-trading results without touching the
entry-signal logic itself. Every check's reason string is returned
regardless of pass/fail so a rejected signal's notification tells you
exactly which condition(s) blocked it — that's what you tune against.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from gold_bot.config import PreTradeFilterConfig
from gold_bot.strategy import ema, rsi


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    reason: str


@dataclass(frozen=True)
class FilterResult:
    passed: bool
    checks: list[CheckResult]

    def reasons(self) -> list[str]:
        return [c.reason for c in self.checks]


class PreTradeFilter:
    def __init__(self, cfg: PreTradeFilterConfig):
        self.cfg = cfg

    def min_higher_tf_bars_required(self) -> int:
        return self.cfg.higher_timeframe_ema_period + 2

    def min_entry_bars_required(self) -> int:
        return max(self.cfg.rsi_period, self.cfg.volume_lookback) + 2

    def evaluate(self, entry_df: pd.DataFrame, higher_tf_df: pd.DataFrame, side: str) -> FilterResult:
        checks = [
            self._trend_check(higher_tf_df, side),
            self._rsi_check(entry_df, side),
            self._volume_spike_check(entry_df),
        ]
        return FilterResult(passed=all(c.passed for c in checks), checks=checks)

    def _trend_check(self, higher_tf_df: pd.DataFrame, side: str) -> CheckResult:
        c = self.cfg
        if len(higher_tf_df) < self.min_higher_tf_bars_required():
            return CheckResult(False, f"not enough {c.higher_timeframe} history for trend check")

        htf_ema = ema(higher_tf_df["close"], c.higher_timeframe_ema_period)
        htf_price = float(higher_tf_df["close"].iloc[-1])
        htf_ema_now = float(htf_ema.iloc[-1])

        if side == "long":
            passed = htf_price > htf_ema_now
        else:
            passed = htf_price < htf_ema_now
        direction = "above" if htf_price > htf_ema_now else "below"
        return CheckResult(
            passed,
            f"{c.higher_timeframe} trend: price {direction} EMA{c.higher_timeframe_ema_period} "
            f"({htf_price:.2f} vs {htf_ema_now:.2f})",
        )

    def _rsi_check(self, entry_df: pd.DataFrame, side: str) -> CheckResult:
        c = self.cfg
        if len(entry_df) < self.min_entry_bars_required():
            return CheckResult(False, "not enough history for RSI check")

        rsi_now = float(rsi(entry_df["close"], c.rsi_period).iloc[-1])
        if side == "long":
            passed = rsi_now < c.rsi_overbought
        else:
            passed = rsi_now > c.rsi_oversold
        return CheckResult(passed, f"RSI({c.rsi_period})={rsi_now:.1f}")

    def _volume_spike_check(self, entry_df: pd.DataFrame) -> CheckResult:
        c = self.cfg
        if "volume" not in entry_df.columns:
            return CheckResult(False, "no volume data available")
        if len(entry_df) < self.min_entry_bars_required():
            return CheckResult(False, "not enough history for volume check")

        current_volume = float(entry_df["volume"].iloc[-1])
        avg_volume = float(entry_df["volume"].iloc[-(c.volume_lookback + 1):-1].mean())
        if avg_volume <= 0:
            return CheckResult(False, "average volume is zero")

        ratio = current_volume / avg_volume
        passed = ratio >= c.volume_spike_multiplier
        return CheckResult(passed, f"volume {ratio:.2f}x avg({c.volume_lookback}) (need >= {c.volume_spike_multiplier}x)")
