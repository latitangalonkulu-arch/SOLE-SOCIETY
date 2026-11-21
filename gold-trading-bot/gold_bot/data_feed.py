"""Price feed backed by CCXT's public (keyless) market data endpoints.

Works for both paper trading and live trading since it never needs API
credentials — only order placement (in the CCXT broker) needs keys.
Returns OHLCV including volume, which the pre-trade filter's volume-spike
check depends on. This is also why PAXG (traded on real order books with
real volume) is a better fit for a volume-based filter than a forex
spot-rate feed, which typically reports no meaningful volume at all.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class PriceFeed(ABC):
    @abstractmethod
    def get_bars(self, lookback: int, interval: str) -> pd.DataFrame:
        """Return a DataFrame indexed by time, columns open/high/low/close/volume, newest last."""

    @abstractmethod
    def get_last_price(self) -> float:
        """Return the latest tradeable price."""


class CCXTFeed(PriceFeed):
    def __init__(self, exchange_id: str, symbol: str, exchange=None):
        """`exchange` can be injected (e.g. an already-authenticated client
        shared with the broker, or a fake for tests); otherwise a fresh
        public (no API key) client is created for this exchange_id.
        """
        self.symbol = symbol
        if exchange is not None:
            self._exchange = exchange
        else:
            import ccxt

            exchange_class = getattr(ccxt, exchange_id)
            self._exchange = exchange_class()

    def get_bars(self, lookback: int, interval: str) -> pd.DataFrame:
        ohlcv = self._exchange.fetch_ohlcv(self.symbol, timeframe=interval, limit=lookback)
        if not ohlcv:
            raise RuntimeError(f"No OHLCV data returned for {self.symbol} ({interval})")
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df.set_index("timestamp")

    def get_last_price(self) -> float:
        ticker = self._exchange.fetch_ticker(self.symbol)
        return float(ticker["last"])
