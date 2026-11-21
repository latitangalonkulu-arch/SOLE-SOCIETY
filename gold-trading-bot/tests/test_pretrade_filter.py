import pandas as pd
import pytest

from gold_bot.config import PreTradeFilterConfig
from gold_bot.pretrade_filter import PreTradeFilter


def make_filter(**overrides) -> PreTradeFilter:
    defaults = dict(
        enabled=True, higher_timeframe="1h", higher_timeframe_ema_period=5,
        rsi_period=5, rsi_overbought=70, rsi_oversold=30,
        volume_lookback=5, volume_spike_multiplier=1.5,
    )
    defaults.update(overrides)
    return PreTradeFilter(PreTradeFilterConfig(**defaults))


def make_df(closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    n = len(closes)
    volumes = volumes or [100.0] * n
    return pd.DataFrame({
        "open": closes, "high": [c + 0.5 for c in closes], "low": [c - 0.5 for c in closes],
        "close": closes, "volume": volumes,
    })


def test_uptrend_and_volume_spike_passes_long_filter():
    filt = make_filter()
    # Higher timeframe clearly trending up: price well above its EMA.
    htf = make_df([100 + i for i in range(10)])
    # Entry timeframe: calm volume then one big spike on the last bar.
    entry_volumes = [100.0] * 9 + [500.0]
    entry = make_df([100 + i * 0.1 for i in range(10)], entry_volumes)

    result = filt.evaluate(entry, htf, side="long")
    assert result.passed, result.reasons()


def test_downtrend_blocks_long_filter():
    filt = make_filter()
    htf = make_df([100 - i for i in range(10)])  # downtrend
    entry = make_df([100 - i * 0.1 for i in range(10)], [500.0] * 10)

    result = filt.evaluate(entry, htf, side="long")
    assert not result.passed
    assert any("trend" in r for r in result.reasons())


def test_overbought_rsi_blocks_long_filter():
    filt = make_filter(rsi_overbought=60)
    htf = make_df([100 + i for i in range(10)])
    # Relentless gains push RSI to the ceiling.
    entry = make_df([100 + i * 3 for i in range(10)], [500.0] * 10)

    result = filt.evaluate(entry, htf, side="long")
    assert not result.passed
    assert any("RSI" in r for r in result.reasons())


def test_no_volume_spike_blocks_filter():
    filt = make_filter(volume_spike_multiplier=2.0)
    htf = make_df([100 + i for i in range(10)])
    # Flat, unremarkable volume — no spike on the latest bar.
    entry = make_df([100 + i * 0.1 for i in range(10)], [100.0] * 10)

    result = filt.evaluate(entry, htf, side="long")
    assert not result.passed
    assert any("volume" in r for r in result.reasons())


def test_not_enough_higher_tf_history_fails_closed():
    filt = make_filter(higher_timeframe_ema_period=50)
    htf = make_df([100, 101, 102])  # far too short
    entry = make_df([100 + i * 0.1 for i in range(10)], [500.0] * 10)

    result = filt.evaluate(entry, htf, side="long")
    assert not result.passed
