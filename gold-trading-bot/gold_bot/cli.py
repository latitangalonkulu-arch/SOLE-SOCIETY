from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from gold_bot.config import PROJECT_ROOT, load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="gold-bot", description="Gold (XAU/USD) trading bot")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the live/paper trading loop")
    run_p.add_argument("--live", action="store_true",
                        help="Required in addition to BROKER=mt5 in .env to actually place live orders. "
                             "Without this flag, BROKER=mt5 is refused as a safety check.")

    backtest_p = sub.add_parser("backtest", help="Backtest the strategy over historical data")
    backtest_p.add_argument("--period", default="60d", help="yfinance period, e.g. 30d, 60d, 1y")
    backtest_p.add_argument("--interval", default=None, help="Bar interval, defaults to config.yaml's engine.bar_interval")

    sub.add_parser("status", help="Show current position and trade history summary")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = load_config()

    if args.command == "run":
        if cfg.broker.backend == "mt5" and not args.live:
            print(
                "Refusing to start: BROKER=mt5 in .env but --live was not passed.\n"
                "This is a deliberate safety check before the bot can place real orders.\n"
                "Re-run as: python -m gold_bot.cli run --live",
                file=sys.stderr,
            )
            sys.exit(1)
        from gold_bot.engine import build_engine

        engine = build_engine(cfg, PROJECT_ROOT)
        engine.run_forever()

    elif args.command == "backtest":
        import yfinance as yf

        from gold_bot.backtest import run_backtest
        from gold_bot.strategy import EmaRsiAtrStrategy

        interval = args.interval or cfg.engine.bar_interval
        df = yf.Ticker(cfg.symbol.yfinance_ticker).history(period=args.period, interval=interval)
        df = df.rename(columns=str.lower)[["open", "high", "low", "close"]]
        if df.empty:
            print("No historical data returned; try a shorter period or a daily interval.", file=sys.stderr)
            sys.exit(1)

        strategy = EmaRsiAtrStrategy(cfg.strategy)
        result = run_backtest(df, strategy, cfg.broker.paper_starting_balance, cfg.risk.risk_per_trade)
        print(f"Bars: {len(df)} | Period: {args.period} | Interval: {interval}")
        print(f"Trades: {result.trades} | Wins: {result.wins} | Losses: {result.losses} | Win rate: {result.win_rate:.1%}")
        print(f"Total P&L: {result.total_pnl:+.2f} | Max drawdown: {result.max_drawdown:.1%}")

    elif args.command == "status":
        from gold_bot.journal import TradeJournal

        state_path = PROJECT_ROOT / "data" / "paper_state.json"
        if state_path.exists():
            import json

            state = json.loads(state_path.read_text())
            print(f"Paper balance: {state['balance']:.2f}")
            print(f"Open position: {state['position'] or 'none'}")
        else:
            print("No paper trading state yet — run `gold-bot run` first.")

        journal = TradeJournal(PROJECT_ROOT / "data" / "trades.csv")
        summary = journal.summary()
        print(f"Closed trades: {summary['trades']} | Win rate: {summary['win_rate']:.1%} | "
              f"Total P&L: {summary['total_pnl']:+.2f}")


if __name__ == "__main__":
    main()
