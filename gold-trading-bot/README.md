# Gold Trading Bot (PAXG via CCXT)

An automated bot that generates entry/exit signals on tokenized gold
(PAXG, an ERC-20 token backed 1:1 by physical gold) and executes them on
a crypto exchange through [CCXT](https://github.com/ccxt/ccxt), with push
notifications to your phone on every trade. **Starts in paper (simulated)
trading mode — no real money at risk** until you deliberately switch it
to live.

> ⚠️ **Risk disclaimer**: trading can lose money fast. This bot is a
> starting framework, not a proven profitable strategy. Backtest and
> paper-trade for a meaningful stretch of time before ever pointing it at
> a funded live account, and never risk money you can't afford to lose.

> **Long/flat only**: PAXG is traded spot on most exchanges, and spot
> accounts can't short without margin/futures (which this bot doesn't
> use). The bot only ever goes long or stays flat — short signals are
> computed by the strategy but skipped before any order is placed.

## How it works

```
price feed (ccxt)
    -> strategy: EMA crossover decides direction, ATR sets stop/target
    -> pre-trade filter: entry only placed if ALL of these pass:
         1. higher-timeframe trend alignment
         2. RSI not overbought/oversold
         3. current-bar volume spike vs its recent average
    -> risk manager: position sizing, daily loss kill-switch
    -> broker: paper simulator (default) or real CCXT orders
    -> trade journal (CSV) + push notification to your phone
```

- **Strategy** (`gold_bot/strategy.py`): pure EMA-crossover direction —
  long when the fast EMA crosses above the slow EMA, short (skipped live)
  on the opposite cross. Stop-loss/take-profit are set from ATR at entry.
  Exits early if the EMA crosses back the other way — exits are never
  blocked by the pre-trade filter below, only entries are.
- **Pre-trade filter** (`gold_bot/pretrade_filter.py`): the gate requested
  — before any entry signal becomes a real order, it must pass trend
  alignment on a higher timeframe, an RSI check, and a volume-spike check,
  all independently configurable in `config.yaml` under `pretrade_filter:`
  so you can tune them against paper-trading/backtest results without
  touching the entry logic itself. A rejected signal is logged and pushed
  to your phone with the exact reason(s) it failed, so you can see what to
  loosen/tighten.
- **Risk manager** (`gold_bot/risk.py`): sizes every trade to risk a fixed
  % of equity (default 1%) based on entry-to-stop distance, caps
  concurrent positions, and halts new trades for the day after a 3%
  equity drawdown.
- **Broker** (`gold_bot/broker/`): `PaperBroker` simulates fills with a
  virtual balance persisted to `data/paper_state.json`. `CCXTBroker`
  places real market orders on your exchange. Both are long-only, so
  paper trading validates exactly what live trading will be able to do.
  Stop-loss/take-profit are tracked locally and enforced by the engine
  polling and firing a market sell when breached — not a broker-side OCO
  order, so protection only works while this process is running.
- **Notifications** (`gold_bot/notifier/`): pushes an alert to your phone
  on every entry, skipped signal, and exit via
  [ntfy.sh](https://ntfy.sh) (free, no account). Telegram is also
  supported if you'd rather use that.
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

Check `config.yaml`:
- `symbol.exchange_id` / `symbol.symbol` — confirm the exchange you plan
  to eventually trade on actually lists that pair (e.g. Binance lists
  `PAXG/USDT`; verify for whichever exchange you use).
- `pretrade_filter.*` — the defaults are a reasonable starting point, not
  tuned for you. Expect to adjust `higher_timeframe`,
  `volume_spike_multiplier`, and the RSI bounds after reviewing paper
  trades and backtests.

## Running it

**Backtest first** — see how the strategy + pre-trade filter would have
performed on recent history before trusting it with anything, even paper
money:

```bash
python -m gold_bot.cli backtest --interval 15m
python -m gold_bot.cli backtest --interval 15m --no-filter   # compare with the filter off
```

(Capped at ~1000 bars per run — a single exchange API call's worth of
history. Good enough to sanity-check and tune thresholds, not a full
historical research pipeline.)

**Then run paper trading** (simulated fills, real market data from the
exchange's public API, no real money, no API keys needed):

```bash
python -m gold_bot.cli run
```

This polls the price feed every `engine.poll_interval_seconds` (default
60s), evaluates the strategy and pre-trade filter, and opens/closes
simulated positions. Leave it running (e.g. in `tmux`, or as a systemd
service / background process on a small always-on VPS — a cellphone
itself can't reliably host a background Python process, so this is meant
to run on a server and just *notify* your phone). Check in anytime via
the ntfy push alerts, or:

```bash
python -m gold_bot.cli status
```

## Going live (CCXT)

This is the highest-risk step — real orders, real money. Only do this
after you've validated the strategy + filter in backtest and paper mode,
and are comfortable with the risk settings in `config.yaml`.

1. Open an account on an exchange that lists PAXG (check `symbol.symbol`
   in `config.yaml` matches what that exchange actually calls the pair).
2. Create API keys scoped to **spot trading only — no withdrawal
   permission**.
3. In `.env`, set `BROKER=ccxt`, `CCXT_API_KEY`, `CCXT_API_SECRET`, and
   `CCXT_API_PASSWORD` if your exchange requires one (OKX, KuCoin, ...).
4. Run with the explicit live flag — this is a deliberate safety check,
   the bot refuses to place real orders without it:
   ```bash
   python -m gold_bot.cli run --live
   ```

Unlike a broker-side OCO order, stop-loss/take-profit here are enforced
by this process polling and firing a real market sell once breached — if
the bot stops running, an open position's SL/TP will NOT be enforced by
the exchange on its own. Keep the process supervised (systemd restart
policy, a monitoring alert, etc.) if you go live.

## Tests

```bash
pip install pytest
python -m pytest
```

27 unit tests cover: strategy indicator math and crossover signal logic;
the pre-trade filter's trend/RSI/volume checks (including rejection
reasons); risk sizing and the daily-loss kill-switch; the paper broker's
fill/PnL/persistence behavior and long-only constraint; and the CCXT
broker's order placement, equity mark-to-market, and SL/TP enforcement
(exercised against a fake exchange client, so no real credentials or
network are needed to run the suite).

## Notes / limitations

- The data feed (`ccxt` public endpoints) is free and keyless but can be
  rate-limited — fine for validating logic, not a guarantee of your live
  exchange's exact fill conditions.
- The strategy is intentionally simple (EMA/ATR) and unoptimized; the
  pre-trade filter is the main lever for being pickier about entries.
  Treat both as a framework to iterate on, not a finished edge.
- Long/flat only, as noted above — no margin, no futures, no shorting.
- There's no web/mobile dashboard here — "mobile" access is via push
  notifications (ntfy/Telegram) plus `cli status` from wherever the bot
  runs.
