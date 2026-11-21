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
    yfinance_ticker: str
    display_name: str


@dataclass(frozen=True)
class StrategyConfig:
    fast_ema: int
    slow_ema: int
    rsi_period: int
    rsi_overbought: float
    rsi_oversold: float
    atr_period: int
    stop_loss_atr_mult: float
    take_profit_atr_mult: float


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
    backend: str  # "paper" | "mt5"
    paper_starting_balance: float
    mt5_login: int | None
    mt5_password: str | None
    mt5_server: str | None
    mt5_symbol: str | None


@dataclass(frozen=True)
class AppConfig:
    symbol: SymbolConfig
    strategy: StrategyConfig
    risk: RiskConfig
    engine: EngineConfig
    notifier: NotifierConfig
    broker: BrokerConfig


def load_config(config_path: Path | None = None) -> AppConfig:
    load_dotenv(PROJECT_ROOT / ".env")

    path = config_path or (PROJECT_ROOT / "config.yaml")
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    mt5_login_raw = os.getenv("MT5_LOGIN")

    return AppConfig(
        symbol=SymbolConfig(**raw["symbol"]),
        strategy=StrategyConfig(**raw["strategy"]),
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
            mt5_login=int(mt5_login_raw) if mt5_login_raw else None,
            mt5_password=os.getenv("MT5_PASSWORD") or None,
            mt5_server=os.getenv("MT5_SERVER") or None,
            mt5_symbol=os.getenv("MT5_SYMBOL") or None,
        ),
    )
