"""
Setup:
  env vars required at runtime: MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
  optional: news_calendar.json next to this file - a JSON list like
    [{"time_utc": "2026-12-05T13:30:00", "label": "NFP"}, ...]
    maintained by hand; no news filtering happens without it.

Before going live: verify BotConfig.broker_utc_offset_hours against your
broker's actual server clock (Market Watch -> symbol -> Properties, or
compare a fresh tick's time to real UTC). Every session-window and
news-blackout check depends on this being right.
"""
import csv
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5
import numpy as np
import pandas as pd


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class BotConfig:
    symbol: str = "XAUUSD"
    magic: int = 772025

    # Rule 1 - market / sessions (SA local time)
    session_windows: tuple = ((9, 0, 12, 0), (14, 0, 18, 0))
    friday_cutoff_hour: int = 16
    monday_block_until_hour: int = 10
    sa_utc_offset_hours: float = 2.0
    broker_utc_offset_hours: float = 2.0  # MUST match your broker's server clock

    # Rule 2 - bias
    ema_bias_period: int = 200
    chop_atr_mult: float = 0.3

    # Rule 3 - entries
    ema_pullback_period: int = 21
    pullback_touch_tolerance_mult: float = 0.1  # * ATR(15m)
    sweep_lookback_bars: int = 1

    # Rule 4 - risk
    risk_pct_per_trade: float = 0.01
    sl_min_usd: float = 0.50
    sl_max_usd: float = 1.00
    reward_multiple: float = 2.0
    max_trades_per_day: int = 2
    max_losses_per_day: int = 2
    max_lot_cap: float = 0.05  # hard ceiling regardless of equity/risk math

    # Rule 5 - exits
    stale_trade_hours: float = 2.0
    stale_trade_r_threshold: float = 0.2  # "not moving" if |floating R| < this
    flatten_hour: int = 18

    # Rule 6 - filters
    max_spread_usd: float = 0.35
    consecutive_loss_limit: int = 2
    consecutive_loss_pause_hours: float = 1.0
    news_calendar_path: str = "news_calendar.json"
    news_blackout_minutes: int = 30

    poll_seconds: int = 30
    trade_log_path: str = "gold_bot_trades.csv"


class SmartGoldBot:
    def __init__(self, login, password, server, config: BotConfig = None):
        self.login = login
        self.password = password
        self.server = server
        self.cfg = config or BotConfig()
        self.symbol = self.cfg.symbol
        self.mt5_initialized = False

        self.tracked_positions = {}  # ticket -> {open_time, direction, entry_type, risk_amount}
        self.last_entry_bar_time = None
        self.day_state = {
            "date": None,
            "trades": 0,
            "losses": 0,
            "consecutive_losses": 0,
            "pause_until": None,
        }
        self._news_cache = None

    # ---------------- connection ----------------

    def initialize_mt5(self):
        if not mt5.initialize():
            print("initialize() failed:", mt5.last_error())
            return False
        if not mt5.login(self.login, password=self.password, server=self.server):
            print("login failed:", mt5.last_error())
            mt5.shutdown()
            return False
        if not mt5.symbol_select(self.symbol, True):
            print(f"Could not select {self.symbol}")
            mt5.shutdown()
            return False
        self.mt5_initialized = True
        print("MT5 connected and authorized.")
        return True

    # ---------------- data ----------------

    def fetch_closed_bars(self, timeframe, num_bars):
        # shift=1 skips the still-forming bar, so index -1 is the last *closed* bar
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 1, num_bars)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        return df

    @staticmethod
    def _ema(series, period):
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _atr(df, period=14):
        tr = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                abs(df["high"] - df["close"].shift(1)),
                abs(df["low"] - df["close"].shift(1)),
            ),
        )
        return tr.rolling(period).mean()

    def to_utc(self, server_dt):
        return server_dt - timedelta(hours=self.cfg.broker_utc_offset_hours)

    def to_sa_time(self, server_dt):
        return self.to_utc(server_dt) + timedelta(hours=self.cfg.sa_utc_offset_hours)

    # ---------------- Rule 1: sessions ----------------

    def in_session_window(self, sa_time):
        weekday = sa_time.weekday()  # Mon=0
        if weekday >= 5:
            return False
        if weekday == 0 and sa_time.hour < self.cfg.monday_block_until_hour:
            return False
        if weekday == 4 and sa_time.hour >= self.cfg.friday_cutoff_hour:
            return False
        hm = sa_time.hour * 60 + sa_time.minute
        return any(
            h1 * 60 + m1 <= hm < h2 * 60 + m2
            for h1, m1, h2, m2 in self.cfg.session_windows
        )

    # ---------------- Rule 6: news filter ----------------

    def _load_news_calendar(self):
        if self._news_cache is not None:
            return self._news_cache
        path = self.cfg.news_calendar_path
        events = []
        if os.path.exists(path):
            with open(path) as f:
                raw = json.load(f)
            events = [datetime.fromisoformat(item["time_utc"]) for item in raw]
        else:
            print(f"[news] no calendar file at {path} - news filter is inactive")
        self._news_cache = events
        return events

    def is_news_blackout(self, utc_now):
        window = timedelta(minutes=self.cfg.news_blackout_minutes)
        return any(abs(utc_now - ev) <= window for ev in self._load_news_calendar())

    # ---------------- Rule 2: bias ----------------

    def compute_bias(self, df_1h):
        ema200 = self._ema(df_1h["close"], self.cfg.ema_bias_period)
        atr = self._atr(df_1h)
        close, band = df_1h["close"].iloc[-1], atr.iloc[-1] * self.cfg.chop_atr_mult
        level = ema200.iloc[-1]
        if close > level + band:
            return "BUY"
        if close < level - band:
            return "SELL"
        return "FLAT"

    def trend_agrees(self, df_15m, bias):
        ema = self._ema(df_15m["close"], self.cfg.ema_pullback_period)
        if bias == "BUY":
            return df_15m["close"].iloc[-1] > ema.iloc[-1]
        if bias == "SELL":
            return df_15m["close"].iloc[-1] < ema.iloc[-1]
        return False

    # ---------------- Rule 3: entries ----------------

    def check_pullback_entry(self, df_15m, bias):
        ema = self._ema(df_15m["close"], self.cfg.ema_pullback_period)
        atr = self._atr(df_15m)
        touch_bar, confirm_bar = df_15m.iloc[-2], df_15m.iloc[-1]
        touch_ema, confirm_ema = ema.iloc[-2], ema.iloc[-1]
        tol = atr.iloc[-1] * self.cfg.pullback_touch_tolerance_mult

        if bias == "BUY":
            touched = touch_bar["low"] <= touch_ema + tol
            confirmed = confirm_bar["close"] > confirm_ema and confirm_bar["close"] > confirm_bar["open"]
            return touched and confirmed
        if bias == "SELL":
            touched = touch_bar["high"] >= touch_ema - tol
            confirmed = confirm_bar["close"] < confirm_ema and confirm_bar["close"] < confirm_bar["open"]
            return touched and confirmed
        return False

    def check_sweep_entry(self, df_15m, bias):
        n = self.cfg.sweep_lookback_bars
        ref_bar, sweep_bar = df_15m.iloc[-(n + 1)], df_15m.iloc[-1]
        if bias == "BUY":
            return sweep_bar["low"] < ref_bar["low"] and sweep_bar["close"] > ref_bar["low"]
        if bias == "SELL":
            return sweep_bar["high"] > ref_bar["high"] and sweep_bar["close"] < ref_bar["high"]
        return False

    # ---------------- Rule 4: risk ----------------

    def compute_sl_tp(self, df_15m, bias, entry_price):
        ref_bar = df_15m.iloc[-2]
        structural = ref_bar["low"] if bias == "BUY" else ref_bar["high"]
        raw_distance = abs(entry_price - structural)
        distance = min(max(raw_distance, self.cfg.sl_min_usd), self.cfg.sl_max_usd)

        if bias == "BUY":
            sl = entry_price - distance
            tp = entry_price + distance * self.cfg.reward_multiple
        else:
            sl = entry_price + distance
            tp = entry_price - distance * self.cfg.reward_multiple
        return sl, tp, distance

    def compute_lot_size(self, sl_distance_price):
        info = mt5.symbol_info(self.symbol)
        account = mt5.account_info()
        if info is None or account is None or sl_distance_price <= 0:
            return info.volume_min if info else 0.01

        value_per_unit_per_lot = info.trade_tick_value / info.trade_tick_size
        risk_amount = account.equity * self.cfg.risk_pct_per_trade
        raw_lot = risk_amount / (sl_distance_price * value_per_unit_per_lot)

        step = info.volume_step
        steps = math.floor(raw_lot / step + 1e-9)
        lot = max(info.volume_min, steps * step)
        lot = min(lot, info.volume_max, self.cfg.max_lot_cap)
        lot = round(lot, 2)

        actual_risk = lot * sl_distance_price * value_per_unit_per_lot
        if actual_risk > risk_amount * 1.5:
            print(
                f"[risk] broker minimum lot ({info.volume_min}) risks ${actual_risk:.2f}, "
                f"above the {self.cfg.risk_pct_per_trade:.0%} target (${risk_amount:.2f}) on this equity"
            )
        return lot

    # ---------------- execution ----------------

    def _filling_mode(self, info):
        mask = info.filling_mode
        if mask & mt5.SYMBOL_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        if mask & mt5.SYMBOL_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    def execute_trade(self, order_type, volume, sl, tp, comment="SmartGoldBot"):
        info = mt5.symbol_info(self.symbol)
        if info is None:
            print("Symbol not found")
            return None
        if not info.visible and not mt5.symbol_select(self.symbol, True):
            print("Failed to select symbol")
            return None

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            print("No tick data")
            return None
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

        digits = info.digits
        price, sl, tp = round(price, digits), round(sl, digits), round(tp, digits)

        min_stop = info.trade_stops_level * info.point
        if min_stop > 0:
            if order_type == mt5.ORDER_TYPE_BUY:
                sl = min(sl, price - min_stop)
                tp = max(tp, price + min_stop)
            else:
                sl = max(sl, price + min_stop)
                tp = min(tp, price - min_stop)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": self.cfg.magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(info),
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            code = result.retcode if result else mt5.last_error()
            print(f"Order failed, retcode={code}")
            return None

        print(f"Order filled: ticket={result.order} price={result.price} vol={volume}")
        return result

    def _close_position(self, pos, reason):
        info = mt5.symbol_info(self.symbol)
        tick = mt5.symbol_info_tick(self.symbol)
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": self.cfg.magic,
            "comment": f"close:{reason}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(info),
        }
        result = mt5.order_send(request)
        code = result.retcode if result else mt5.last_error()
        print(f"Closing #{pos.ticket} ({reason}): retcode={code}")

    # ---------------- Rule 5: position management ----------------

    def manage_open_positions(self, server_now):
        sa_now = self.to_sa_time(server_now)
        positions = mt5.positions_get(symbol=self.symbol) or []
        open_tickets = {p.ticket for p in positions}

        for pos in positions:
            if pos.magic != self.cfg.magic:
                continue
            meta = self.tracked_positions.get(pos.ticket)
            if meta is None:
                continue

            age_hours = (server_now - meta["open_time"]).total_seconds() / 3600
            floating_r = pos.profit / meta["risk_amount"] if meta["risk_amount"] else 0

            should_close, reason = False, ""
            if sa_now.hour >= self.cfg.flatten_hour:
                should_close, reason = True, "session flatten (18:00 SA)"
            elif age_hours >= self.cfg.stale_trade_hours and abs(floating_r) < self.cfg.stale_trade_r_threshold:
                should_close, reason = True, "stale / not moving"

            if should_close:
                self._close_position(pos, reason)

        for ticket in list(self.tracked_positions):
            if ticket not in open_tickets:
                self._record_closed_trade(ticket)

    def _record_closed_trade(self, ticket):
        meta = self.tracked_positions.pop(ticket, None) or {}
        deals = mt5.history_deals_get(position=ticket)
        profit = sum(d.profit + d.swap + d.commission for d in deals) if deals else 0.0

        if profit < 0:
            self.day_state["losses"] += 1
            self.day_state["consecutive_losses"] += 1
            if self.day_state["consecutive_losses"] >= self.cfg.consecutive_loss_limit:
                self.day_state["pause_until"] = _utcnow() + timedelta(
                    hours=self.cfg.consecutive_loss_pause_hours
                )
                print(f"[risk] {self.day_state['consecutive_losses']} losses in a row - pausing new entries")
        else:
            self.day_state["consecutive_losses"] = 0

        self._log_trade(ticket, meta, profit)

    def _log_trade(self, ticket, meta, profit):
        path = self.cfg.trade_log_path
        is_new = not os.path.exists(path)
        with open(path, "a", newline="") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(["ticket", "direction", "entry_type", "open_time", "close_time", "profit"])
            writer.writerow([
                ticket, meta.get("direction"), meta.get("entry_type"),
                meta.get("open_time"), _utcnow(), round(profit, 2),
            ])

    # ---------------- daily state / filters ----------------

    def update_daily_state(self, sa_now):
        today = sa_now.date()
        if self.day_state["date"] != today:
            self.day_state.update({
                "date": today,
                "trades": 0,
                "losses": 0,
                "consecutive_losses": 0,
                "pause_until": None,
            })

    def trading_allowed(self, utc_now, sa_now, spread):
        if self.day_state["pause_until"] and utc_now < self.day_state["pause_until"]:
            return False, "consecutive-loss pause"
        if self.day_state["trades"] >= self.cfg.max_trades_per_day:
            return False, "max trades/day reached"
        if self.day_state["losses"] >= self.cfg.max_losses_per_day:
            return False, "max losses/day reached"
        if not self.in_session_window(sa_now):
            return False, "outside session window"
        if self.is_news_blackout(utc_now):
            return False, "news blackout"
        if spread > self.cfg.max_spread_usd:
            return False, "spread too wide"
        return True, ""

    # ---------------- main loop ----------------

    def run_cycle(self):
        df_1h = self.fetch_closed_bars(mt5.TIMEFRAME_H1, 250)
        df_15m = self.fetch_closed_bars(mt5.TIMEFRAME_M15, 60)
        tick = mt5.symbol_info_tick(self.symbol)
        if df_1h is None or df_15m is None or tick is None:
            return

        server_now = datetime.fromtimestamp(tick.time, tz=timezone.utc).replace(tzinfo=None)
        sa_now = self.to_sa_time(server_now)
        utc_now = self.to_utc(server_now)

        self.update_daily_state(sa_now)
        self.manage_open_positions(server_now)

        spread = tick.ask - tick.bid
        allowed, reason = self.trading_allowed(utc_now, sa_now, spread)
        if not allowed:
            return

        current_bar_time = df_15m.index[-1]
        if self.last_entry_bar_time == current_bar_time:
            return  # already acted on this closed 15m bar

        bias = self.compute_bias(df_1h)
        if bias == "FLAT" or not self.trend_agrees(df_15m, bias):
            return

        if self.check_sweep_entry(df_15m, bias):
            entry_type = "sweep"
        elif self.check_pullback_entry(df_15m, bias):
            entry_type = "pullback"
        else:
            return

        order_type = mt5.ORDER_TYPE_BUY if bias == "BUY" else mt5.ORDER_TYPE_SELL
        entry_price = tick.ask if bias == "BUY" else tick.bid
        sl, tp, distance = self.compute_sl_tp(df_15m, bias, entry_price)
        lot = self.compute_lot_size(distance)

        result = self.execute_trade(order_type, lot, sl, tp, comment=f"{bias}:{entry_type}")
        self.last_entry_bar_time = current_bar_time  # one attempt per bar, win or lose
        if result is not None:
            self.day_state["trades"] += 1
            account = mt5.account_info()
            risk_amount = account.equity * self.cfg.risk_pct_per_trade if account else lot * distance
            self.tracked_positions[result.order] = {
                "open_time": server_now,
                "direction": bias,
                "entry_type": entry_type,
                "risk_amount": risk_amount,
            }


if __name__ == "__main__":
    login = int(os.environ.get("MT5_LOGIN", "0"))
    password = os.environ.get("MT5_PASSWORD", "")
    server = os.environ.get("MT5_SERVER", "")

    bot = SmartGoldBot(login, password, server)
    if bot.initialize_mt5():
        while True:
            try:
                bot.run_cycle()
            except Exception as exc:
                print("cycle error:", exc)
            time.sleep(bot.cfg.poll_seconds)
