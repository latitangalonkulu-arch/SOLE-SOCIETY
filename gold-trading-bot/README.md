# Gold Trading Bot (XAU/USD)

An automated bot that generates entry/exit signals on gold and executes
them through a pluggable broker backend, with push notifications to your
phone on every trade. **Starts in paper (simulated) trading mode — no
real money at risk** until you deliberately switch it to live.

> ⚠️ **Risk disclaimer**: trading leveraged gold CFDs can lose money fast.
> This bot is a starting framework, not a proven profitable strategy.
> Backtest and paper-trade for a meaningful stretch of time before ever
> pointing it at a funded live account, and never risk money you can't
> afford to lose.

## How it works

```
price feed  ->  strategy (EMA cross + RSI filter + ATR stop/target)
            ->  risk manager (position sizing, daily loss kill-switch)
            ->  broker (paper simulator today, MT5 adapter for later)
            ->  trade journal (CSV) + push notification to your phone
```

- **Strategy** (`gold_bot/strategy.py`): enters long when the fast EMA
  crosses above the slow EMA (and RSI isn't overbought), enters short on
  the opposite crossover (RSI not oversold). Stop-loss/take-profit are set
  from ATR at entry. Exits early if the EMA crosses back the other way.
- **Risk manager** (`gold_bot/risk.py`): sizes every trade to risk a fixed
  % of equity (default 1%) based on entry-to-stop distance, caps
  concurrent positions, and halts new trades for the day after a 3%
  equity drawdown.
- **Broker** (`gold_bot/broker/`): `PaperBroker` simulates fills with a
  virtual balance persisted to `data/paper_state.json`. `MT5Broker` is a
  real adapter for MetaTrader 5 — see "Going live" below.
- **Notifications** (`gold_bot/notifier/`): pushes an alert to your phone
  on every entry and exit via [ntfy.sh](https://ntfy.sh) (free, no
  account). Telegram is also supported if you'd rather use that.
- **Journal** (`gold_bot/journal.py`): every closed trade is appended to
  `data/trades.csv` so you can review performance from your phone (any
  spreadsheet/file-viewer app opens a CSV).

## Setup

```bash
cd gold-trading-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
1. Set `NTFY_TOPIC` to something unique/hard-to-guess (it's a public
   pub-sub topic name — anyone who knows it can see your alerts).
2. Install the **ntfy** app on your phone (Android/iOS), subscribe to that
   same topic name, and you'll get a push notification for every trade.
3. Leave `BROKER=paper` for now.

Tune strategy/risk parameters in `config.yaml` if you want (defaults are
reasonable but arbitrary — nothing here is tuned/optimized for gold
specifically).

## Running it

**Backtest first** — see how the strategy would have performed on recent
history before trusting it with anything, even paper money:

```bash
python -m gold_bot.cli backtest --period 60d --interval 5m
```

**Then run paper trading** (simulated fills, real market data, no real
money):

```bash
python -m gold_bot.cli run
```

This polls the price feed every `engine.poll_interval_seconds` (default
60s), evaluates the strategy, and opens/closes simulated positions. Leave
it running (e.g. in `tmux`, or as a systemd service / background process
on a small VPS or always-on machine — a cellphone itself can't run a
background Python process reliably, so this is meant to run on a server
and just *notify* your phone). Check in anytime from your phone via the
ntfy push alerts, or:

```bash
python -m gold_bot.cli status
```

## Going live (MetaTrader 5)

This is the highest-risk step — real orders, real money. Only do this
after you've validated the strategy in backtest + paper mode and are
comfortable with the risk settings in `config.yaml`.

1. You need a broker account that supports gold (XAU/USD) CFDs and offers
   MetaTrader 5, plus a Windows machine or Windows VPS to run the MT5
   terminal (the `MetaTrader5` Python package talks to a **local, running,
   logged-in terminal** — it is not a remote API, so this cannot run from
   this cloud container or from your phone directly).
2. On that machine: install and log into the MT5 terminal, then
   `pip install MetaTrader5`.
3. In `.env`, set `BROKER=mt5` and fill in `MT5_LOGIN`, `MT5_PASSWORD`,
   `MT5_SERVER`, `MT5_SYMBOL` (the broker's exact gold symbol, e.g.
   `XAUUSD`).
4. Run with the explicit live flag — this is a deliberate safety check,
   the bot refuses to place real orders without it:
   ```bash
   python -m gold_bot.cli run --live
   ```

Stop-loss and take-profit are attached to the order itself, so the
broker's servers enforce them even if this process or your network drops
— it doesn't rely on the bot staying online to protect you, but a dead
bot process also won't open any *new* trades or manage anything beyond
the fixed SL/TP.

## Tests

```bash
pip install pytest
python -m pytest
```

16 unit tests cover the strategy's indicator math and signal logic, risk
sizing/kill-switch, and the paper broker's fill/PnL/persistence behavior.

## Notes / limitations

- The paper broker's data feed (`yfinance`) is free and keyless but can
  lag real-time by minutes and occasionally rate-limits — fine for
  validating logic, not a substitute for your live broker's real feed.
- The strategy is intentionally simple (EMA/RSI/ATR) and unoptimized. Treat
  it as a framework to iterate on, not a finished edge.
- There's no web/mobile dashboard here — "mobile" access is via push
  notifications (ntfy/Telegram) plus `cli status` from wherever the bot
  runs. If you later want an interactive phone dashboard, the engine/
  broker/journal modules are already decoupled enough to put a small web
  UI in front of them.
