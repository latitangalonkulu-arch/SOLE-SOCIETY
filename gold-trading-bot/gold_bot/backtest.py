"""Walk a strategy over historical bars bar-by-bar (no look-ahead) and
report simple performance stats. Use this before trusting a paper-trading
run, and before ever switching to live.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from gold_bot.strategy import Action, EmaRsiAtrStrategy


@dataclass
class BacktestResult:
    trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    equity_curve: list[float]


def run_backtest(df: pd.DataFrame, strategy: EmaRsiAtrStrategy, starting_equity: float = 10000.0,
                  risk_per_trade: float = 0.01) -> BacktestResult:
    min_bars = strategy.min_bars_required()
    equity = starting_equity
    equity_curve = [equity]
    peak = equity
    max_dd = 0.0

    side = None
    units = 0.0
    entry_price = 0.0
    stop_loss = None
    take_profit = None

    pnls: list[float] = []

    for i in range(min_bars, len(df)):
        window = df.iloc[: i + 1]
        price = float(window["close"].iloc[-1])

        if side is not None:
            hit = None
            if side == "long":
                if price <= stop_loss:
                    hit = stop_loss
                elif price >= take_profit:
                    hit = take_profit
            else:
                if price >= stop_loss:
                    hit = stop_loss
                elif price <= take_profit:
                    hit = take_profit
            if hit is not None:
                pnl = (hit - entry_price) * units if side == "long" else (entry_price - hit) * units
                equity += pnl
                pnls.append(pnl)
                side = None

        signal = strategy.generate_signal(window, side)

        if signal.action == Action.EXIT and side is not None:
            pnl = (price - entry_price) * units if side == "long" else (entry_price - price) * units
            equity += pnl
            pnls.append(pnl)
            side = None

        elif signal.action in (Action.ENTER_LONG, Action.ENTER_SHORT) and side is None:
            new_side = "long" if signal.action == Action.ENTER_LONG else "short"
            stop_distance = abs(signal.price - signal.stop_loss)
            if stop_distance > 0:
                risk_amount = equity * risk_per_trade
                units = risk_amount / stop_distance
                side = new_side
                entry_price = signal.price
                stop_loss = signal.stop_loss
                take_profit = signal.take_profit

        equity_curve.append(equity)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0.0)

    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p <= 0)
    return BacktestResult(
        trades=len(pnls), wins=wins, losses=losses,
        win_rate=round(wins / len(pnls), 3) if pnls else 0.0,
        total_pnl=round(sum(pnls), 2), max_drawdown=round(max_dd, 4),
        equity_curve=equity_curve,
    )
