"""Price feeds that hand OHLCV bars to the strategy engine.

YFinanceFeed is used for paper trading (free, no API key, delayed/15-min
data — fine for validating a strategy, not for latency-sensitive live
execution). MT5Feed reads bars straight from a running MetaTrader5
terminal and is only usable once BROKER=mt5 on a machine with that
terminal logged in.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class PriceFeed(ABC):
    @abstractmethod
    def get_bars(self, lookback: int, interval: str) -> pd.DataFrame:
        """Return a DataFrame indexed by time with columns open/high/low/close, newest last."""

    @abstractmethod
    def get_last_price(self) -> float:
        """Return the latest tradeable price."""


class YFinanceFeed(PriceFeed):
    def __init__(self, ticker: str):
        self.ticker = ticker

    def get_bars(self, lookback: int, interval: str) -> pd.DataFrame:
        import yfinance as yf

        # yfinance wants a period string, not a bar count; over-fetch and trim.
        period = _period_for(lookback, interval)
        df = yf.Ticker(self.ticker).history(period=period, interval=interval)
        if df.empty:
            raise RuntimeError(f"No data returned for {self.ticker} ({interval}, {period})")
        df = df.rename(columns=str.lower)[["open", "high", "low", "close"]]
        return df.tail(lookback)

    def get_last_price(self) -> float:
        df = self.get_bars(lookback=1, interval="1m")
        return float(df["close"].iloc[-1])


def _period_for(lookback: int, interval: str) -> str:
    """Pick a yfinance `period` long enough to contain `lookback` bars of `interval`."""
    minutes_per_bar = {
        "1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30,
        "60m": 60, "1h": 60, "1d": 60 * 24,
    }.get(interval, 5)
    needed_minutes = minutes_per_bar * lookback
    needed_days = max(1, needed_minutes // (60 * 24) + 1)
    # yfinance intraday data is capped at ~60 days of history.
    needed_days = min(needed_days, 59)
    if interval in ("1m",):
        needed_days = min(needed_days, 6)  # 1m data capped at ~7 days
    return f"{needed_days}d"


class MT5Feed(PriceFeed):
    """Reads bars from a locally-running, logged-in MetaTrader5 terminal.

    Requires the `MetaTrader5` package and only works on the machine where
    that terminal is installed (Windows, or a Windows VPS) — it cannot run
    inside this cloud container.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        try:
            import MetaTrader5 as mt5  # noqa: N814
        except ImportError as e:
            raise RuntimeError(
                "MetaTrader5 package not installed. Run `pip install MetaTrader5` "
                "on the Windows machine/VPS that has the MT5 terminal."
            ) from e
        self._mt5 = mt5

    def get_bars(self, lookback: int, interval: str) -> pd.DataFrame:
        timeframe = _MT5_TIMEFRAMES.get(interval)
        if timeframe is None:
            raise ValueError(f"Unsupported interval for MT5: {interval}")
        rates = self._mt5.copy_rates_from_pos(self.symbol, timeframe, 0, lookback)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"MT5 returned no rates for {self.symbol}: {self._mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.set_index("time").rename(columns={"open": "open", "high": "high", "low": "low", "close": "close"})
        return df[["open", "high", "low", "close"]]

    def get_last_price(self) -> float:
        tick = self._mt5.symbol_info_tick(self.symbol)
        if tick is None:
            raise RuntimeError(f"MT5 could not get tick for {self.symbol}: {self._mt5.last_error()}")
        return float(tick.bid)


_MT5_TIMEFRAMES = {}
try:
    import MetaTrader5 as _mt5  # noqa: N814

    _MT5_TIMEFRAMES = {
        "1m": _mt5.TIMEFRAME_M1,
        "5m": _mt5.TIMEFRAME_M5,
        "15m": _mt5.TIMEFRAME_M15,
        "30m": _mt5.TIMEFRAME_M30,
        "1h": _mt5.TIMEFRAME_H1,
        "1d": _mt5.TIMEFRAME_D1,
    }
except ImportError:
    pass
