"""Real broker adapter over CCXT, for trading PAXG (or another
exchange-listed gold token) on a spot crypto exchange.

Spot accounts generally can't short without margin/futures (which this
bot doesn't use), so this broker is long/flat only — open_position("short",
...) raises. Stop-loss/take-profit are NOT attached to the exchange order;
most spot markets don't support that reliably through CCXT's unified API
across exchanges, so — like PaperBroker — SL/TP are tracked locally and
enforced by the engine calling check_stop_take() every poll, which places
a real market sell once the threshold is breached. That means protection
only works while this process is running and polling; it is not a
broker-side guarantee the way an OCO order or MT5's server-side SL/TP is.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from gold_bot.broker.base import Broker, ClosedTrade, Position
from gold_bot.broker.state import position_from_dict, position_to_dict


class CCXTBroker(Broker):
    supports_short = False

    def __init__(
        self,
        exchange_id: str,
        symbol: str,
        state_path: Path,
        api_key: str | None = None,
        api_secret: str | None = None,
        api_password: str | None = None,
        exchange=None,
    ):
        """`exchange` can be injected (a real authenticated ccxt client, or
        a fake for tests); otherwise one is built from the given credentials.
        """
        self.symbol = symbol
        self.base_currency, self.quote_currency = symbol.split("/")
        self.state_path = state_path

        if exchange is not None:
            self._exchange = exchange
        else:
            import ccxt

            if not (api_key and api_secret):
                raise RuntimeError(
                    "BROKER=ccxt requires CCXT_API_KEY and CCXT_API_SECRET in .env "
                    "(create read+trade API keys on your exchange account)."
                )
            exchange_class = getattr(ccxt, exchange_id)
            params = {"apiKey": api_key, "secret": api_secret}
            if api_password:
                params["password"] = api_password
            self._exchange = exchange_class(params)

        self._position: Position | None = None
        self._load()

    # --- persistence -------------------------------------------------------
    def _load(self) -> None:
        if not self.state_path.exists():
            return
        import json

        data = json.loads(self.state_path.read_text())
        self._position = position_from_dict(data.get("position"))

    def _save(self) -> None:
        import json

        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({"position": position_to_dict(self._position)}, indent=2))

    # --- Broker interface ----------------------------------------------------
    def get_equity(self) -> float:
        balance = self._exchange.fetch_balance()
        quote_total = float(balance.get("total", {}).get(self.quote_currency, 0.0))
        base_total = float(balance.get("total", {}).get(self.base_currency, 0.0))
        if base_total <= 0:
            return quote_total
        price = float(self._exchange.fetch_ticker(self.symbol)["last"])
        return quote_total + base_total * price

    def get_open_position(self) -> Position | None:
        return self._position

    def open_position(self, side: str, units: float, price: float,
                       stop_loss: float | None, take_profit: float | None) -> Position:
        if side == "short":
            raise ValueError(
                f"{self.__class__.__name__} is spot/long-only and cannot open a short position"
            )
        if self._position is not None:
            raise RuntimeError("Position already open; close it before opening a new one")

        order = self._exchange.create_market_buy_order(self.symbol, units)
        filled_price = float(order.get("average") or order.get("price") or price)
        filled_units = float(order.get("filled") or order.get("amount") or units)

        self._position = Position(
            side="long", units=filled_units, entry_price=filled_price,
            stop_loss=stop_loss, take_profit=take_profit,
            opened_at=datetime.now(timezone.utc),
        )
        self._save()
        return self._position

    def close_position(self, price: float, reason: str) -> ClosedTrade | None:
        if self._position is None:
            return None
        pos = self._position

        order = self._exchange.create_market_sell_order(self.symbol, pos.units)
        exit_price = float(order.get("average") or order.get("price") or price)

        pnl = (exit_price - pos.entry_price) * pos.units
        trade = ClosedTrade(
            side=pos.side, units=pos.units, entry_price=pos.entry_price,
            exit_price=exit_price, opened_at=pos.opened_at,
            closed_at=datetime.now(timezone.utc), pnl=pnl, reason=reason,
        )
        self._position = None
        self._save()
        return trade

    def check_stop_take(self, current_price: float) -> ClosedTrade | None:
        pos = self._position
        if pos is None:
            return None
        if pos.stop_loss is not None and current_price <= pos.stop_loss:
            return self.close_position(current_price, "stop_loss hit")
        if pos.take_profit is not None and current_price >= pos.take_profit:
            return self.close_position(current_price, "take_profit hit")
        return None
