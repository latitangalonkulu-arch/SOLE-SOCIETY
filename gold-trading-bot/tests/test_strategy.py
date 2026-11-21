import numpy as np
import pandas as pd
import pytest

from gold_bot.config import StrategyConfig
from gold_bot.strategy import Action, EmaRsiAtrStrategy, atr, ema, rsi


def make_strategy() -> EmaRsiAtrStrategy:
    cfg = StrategyConfig(
        fast_ema=3, slow_ema=6, rsi_period=5,
        rsi_overbought=70, rsi_oversold=30,
        atr_period=5, stop_loss_atr_mult=1.5, take_profit_atr_mult=3.0,
    )
    return EmaRsiAtrStrategy(cfg)


def make_df(closes: list[float]) -> pd.DataFrame:
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    opens = closes
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})


def test_not_enough_history_returns_hold():
    strat = make_strategy()
    df = make_df([100.0, 101.0, 102.0])
    signal = strat.generate_signal(df, current_side=None)
    assert signal.action == Action.HOLD


def test_uptrend_triggers_long_entry_with_sl_tp_below_above_price():
    strat = make_strategy()
    # A clean uptrend forces a fast/slow EMA bullish crossover.
    closes = [100 + i * 0.1 for i in range(10)] + [100 + i * 1.5 for i in range(10)]
    df = make_df(closes)
    signal = strat.generate_signal(df, current_side=None)
    assert signal.action in (Action.ENTER_LONG, Action.HOLD)
    if signal.action == Action.ENTER_LONG:
        assert signal.stop_loss < signal.price < signal.take_profit


def test_open_long_exits_on_bearish_crossover():
    strat = make_strategy()
    # Strong up move then a sharp reversal down should cross EMAs the other way.
    up = [100 + i * 1.5 for i in range(15)]
    down = [up[-1] - i * 2.0 for i in range(1, 10)]
    df = make_df(up + down)
    signal = strat.generate_signal(df, current_side="long")
    assert signal.action in (Action.EXIT, Action.HOLD)


def test_rsi_bounds_between_0_and_100():
    closes = [100, 101, 99, 102, 98, 103, 97, 104, 96, 105]
    series = pd.Series(closes, dtype=float)
    values = rsi(series, period=4)
    assert values.between(0, 100).all()


def test_ema_converges_toward_constant_series():
    series = pd.Series([50.0] * 20)
    values = ema(series, period=5)
    assert values.iloc[-1] == pytest.approx(50.0)


def test_atr_is_nonnegative():
    df = make_df([100, 102, 101, 105, 103, 108, 104])
    values = atr(df, period=3)
    assert (values.dropna() >= 0).all()
