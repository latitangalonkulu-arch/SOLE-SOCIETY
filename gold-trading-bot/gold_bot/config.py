"""Loads config.yaml + .env into typed, immutable config objects."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class SymbolConfig:
    exchange_id: str  # ccxt exchange id, e.g. "binance", "kraken"
    symbol: str  # ccxt market symbol, e.g. "PAXG/USDT"
    display_name: str


@dataclass(frozen=True)
class StrategyConfig:
    fast_ema: int
    slow_ema: int
    atr_period: int
    stop_loss_atr_mult: float
    take_profit_atr_mult: float


@dataclass(frozen=True)
class PreTradeFilterConfig:
    """Independent confirmation gate applied before any entry is placed.

    Kept separate from StrategyConfig so these thresholds can be tuned
    against paper-trading results without touching entry-signal logic.
    """
    enabled: bool
    higher_timeframe: str  # ccxt timeframe string, e.g. "1h"
    higher_timeframe_ema_period: int
    rsi_period: int
    rsi_overbought: float
    rsi_oversold: float
    volume_lookback: int
    volume_spike_multiplier: float


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade: float
    max_open_positions: int
    max_daily_loss_pct: float


@dataclass(frozen=True)
class EngineConfig:
    poll_interval_seconds: int
    lookback_bars: int
    bar_interval: str


@dataclass(frozen=True)
class NotifierConfig:
    ntfy_topic: str | None
    ntfy_server: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None


@dataclass(frozen=True)
class BrokerConfig:
    backend: str  # "paper" | "ccxt"
    paper_starting_balance: float
    ccxt_api_key: str | None
    ccxt_api_secret: str | None
    ccxt_api_password: str | None  # some exchanges (OKX, KuCoin, ...) require this


@dataclass(frozen=True)
class AppConfig:
    symbol: SymbolConfig
    strategy: StrategyConfig
    pretrade_filter: PreTradeFilterConfig
    risk: RiskConfig
    engine: EngineConfig
    notifier: NotifierConfig
    broker: BrokerConfig


def load_config(config_path: Path | None = None) -> AppConfig:
    load_dotenv(PROJECT_ROOT / ".env")

    path = config_path or (PROJECT_ROOT / "config.yaml")
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    return AppConfig(
        symbol=SymbolConfig(**raw["symbol"]),
        strategy=StrategyConfig(**raw["strategy"]),
        pretrade_filter=PreTradeFilterConfig(**raw["pretrade_filter"]),
        risk=RiskConfig(**raw["risk"]),
        engine=EngineConfig(**raw["engine"]),
        notifier=NotifierConfig(
            ntfy_topic=os.getenv("NTFY_TOPIC") or None,
            ntfy_server=os.getenv("NTFY_SERVER", "https://ntfy.sh"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        ),
        broker=BrokerConfig(
            backend=os.getenv("BROKER", "paper"),
            paper_starting_balance=float(os.getenv("PAPER_STARTING_BALANCE", "10000")),
            ccxt_api_key=os.getenv("CCXT_API_KEY") or None,
            ccxt_api_secret=os.getenv("CCXT_API_SECRET") or None,
            ccxt_api_password=os.getenv("CCXT_API_PASSWORD") or None,
        ),
    )
