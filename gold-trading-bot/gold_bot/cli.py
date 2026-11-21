from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from gold_bot.config import PROJECT_ROOT, load_config

# ccxt's single fetch_ohlcv call is capped by the exchange (commonly
# ~1000 candles); good enough to sanity-check the strategy + filter, not
# a substitute for a dedicated historical-data pipeline.
MAX_BACKTEST_BARS = 1000


def main() -> None:
    parser = argparse.ArgumentParser(prog="gold-bot", description="Gold/PAXG trading bot")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the live/paper trading loop")
    run_p.add_argument("--live", action="store_true",
                        help="Required in addition to BROKER=ccxt in .env to actually place live orders. "
                             "Without this flag, BROKER=ccxt is refused as a safety check.")

    backtest_p = sub.add_parser("backtest", help="Backtest the strategy + pre-trade filter over historical data")
    backtest_p.add_argument("--bars", type=int, default=MAX_BACKTEST_BARS,
                             help=f"Number of entry-timeframe bars to fetch (max {MAX_BACKTEST_BARS})")
    backtest_p.add_argument("--interval", default=None,
                             help="Entry-timeframe bar interval, defaults to config.yaml's engine.bar_interval")
    backtest_p.add_argument("--no-filter", action="store_true",
                             help="Disable the pre-trade filter for this backtest run, to compare against")

    sub.add_parser("status", help="Show current position and trade history summary")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = load_config()

    if args.command == "run":
        if cfg.broker.backend == "ccxt" and not args.live:
            print(
                "Refusing to start: BROKER=ccxt in .env but --live was not passed.\n"
                "This is a deliberate safety check before the bot can place real orders.\n"
                "Re-run as: python -m gold_bot.cli run --live",
                file=sys.stderr,
            )
            sys.exit(1)
        from gold_bot.engine import build_engine

        engine = build_engine(cfg, PROJECT_ROOT)
        engine.run_forever()

    elif args.command == "backtest":
        from gold_bot.backtest import run_backtest
        from gold_bot.data_feed import CCXTFeed
        from gold_bot.pretrade_filter import PreTradeFilter
        from gold_bot.strategy import EmaAtrStrategy

        interval = args.interval or cfg.engine.bar_interval
        bars = min(args.bars, MAX_BACKTEST_BARS)

        feed = CCXTFeed(cfg.symbol.exchange_id, cfg.symbol.symbol)
        df = feed.get_bars(bars, interval)
        if df.empty:
            print("No historical data returned.", file=sys.stderr)
            sys.exit(1)

        strategy = EmaAtrStrategy(cfg.strategy)

        pretrade_filter = None
        higher_tf_df = None
        if cfg.pretrade_filter.enabled and not args.no_filter:
            pretrade_filter = PreTradeFilter(cfg.pretrade_filter)
            higher_tf_df = feed.get_bars(bars, cfg.pretrade_filter.higher_timeframe)

        result = run_backtest(
            df, strategy, cfg.broker.paper_starting_balance, cfg.risk.risk_per_trade,
            allow_short=False,  # PAXG is spot/long-only on most exchanges
            pretrade_filter=pretrade_filter, higher_tf_df=higher_tf_df,
        )
        print(f"Bars: {len(df)} | Interval: {interval} | Pre-trade filter: {'on' if pretrade_filter else 'off'}")
        print(f"Trades: {result.trades} | Wins: {result.wins} | Losses: {result.losses} | Win rate: {result.win_rate:.1%}")
        print(f"Total P&L: {result.total_pnl:+.2f} | Max drawdown: {result.max_drawdown:.1%}")
        if pretrade_filter:
            print(f"Entry signals rejected by filter: {result.filtered_out}")

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
