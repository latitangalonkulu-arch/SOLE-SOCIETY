from pathlib import Path

import pytest

from gold_bot.broker.ccxt_broker import CCXTBroker


class FakeExchange:
    """Minimal stand-in for a ccxt exchange client, so these tests exercise
    CCXTBroker's own logic without needing real credentials or network.
    """

    def __init__(self, fill_price: float = 2000.0):
        self.fill_price = fill_price
        self.balances = {"PAXG": 0.0, "USDT": 10000.0}
        self.buy_calls = []
        self.sell_calls = []

    def create_market_buy_order(self, symbol, amount):
        self.buy_calls.append((symbol, amount))
        self.balances["USDT"] -= amount * self.fill_price
        self.balances["PAXG"] += amount
        return {"average": self.fill_price, "filled": amount}

    def create_market_sell_order(self, symbol, amount):
        self.sell_calls.append((symbol, amount))
        self.balances["PAXG"] -= amount
        self.balances["USDT"] += amount * self.fill_price
        return {"average": self.fill_price, "filled": amount}

    def fetch_balance(self):
        return {"total": dict(self.balances)}

    def fetch_ticker(self, symbol):
        return {"last": self.fill_price}


@pytest.fixture
def exchange() -> FakeExchange:
    return FakeExchange(fill_price=2000.0)


@pytest.fixture
def broker(tmp_path: Path, exchange: FakeExchange) -> CCXTBroker:
    return CCXTBroker("binance", "PAXG/USDT", tmp_path / "state.json", exchange=exchange)


def test_open_position_places_real_buy_order_and_tracks_fill(broker: CCXTBroker, exchange: FakeExchange):
    pos = broker.open_position("long", units=2, price=1999, stop_loss=1950, take_profit=2100)
    assert exchange.buy_calls == [("PAXG/USDT", 2)]
    assert pos.entry_price == 2000.0  # uses the exchange's reported fill price, not the signal price
    assert pos.units == 2


def test_opening_short_is_rejected(broker: CCXTBroker):
    with pytest.raises(ValueError):
        broker.open_position("short", units=1, price=2000, stop_loss=2010, take_profit=1980)


def test_close_position_places_sell_and_realizes_pnl(broker: CCXTBroker, exchange: FakeExchange):
    broker.open_position("long", units=2, price=2000, stop_loss=1950, take_profit=2100)
    exchange.fill_price = 2050.0  # price moved up before exit
    trade = broker.close_position(price=2050, reason="manual close")
    assert exchange.sell_calls == [("PAXG/USDT", 2)]
    assert trade.pnl == pytest.approx((2050 - 2000) * 2)
    assert broker.get_open_position() is None


def test_get_equity_marks_open_position_to_market(broker: CCXTBroker, exchange: FakeExchange):
    broker.open_position("long", units=2, price=2000, stop_loss=1950, take_profit=2100)
    exchange.fill_price = 2100.0
    # equity = remaining USDT (10000 - 4000 = 6000) + 2 PAXG * 2100
    assert broker.get_equity() == pytest.approx(6000.0 + 2 * 2100.0)


def test_check_stop_take_closes_on_stop_loss_breach(broker: CCXTBroker, exchange: FakeExchange):
    broker.open_position("long", units=2, price=2000, stop_loss=1950, take_profit=2100)
    exchange.fill_price = 1940.0
    trade = broker.check_stop_take(current_price=1940.0)
    assert trade is not None
    assert trade.reason == "stop_loss hit"
    assert broker.get_open_position() is None


def test_state_persists_across_instances(tmp_path: Path, exchange: FakeExchange):
    state_path = tmp_path / "state.json"
    b1 = CCXTBroker("binance", "PAXG/USDT", state_path, exchange=exchange)
    b1.open_position("long", units=2, price=2000, stop_loss=1950, take_profit=2100)

    b2 = CCXTBroker("binance", "PAXG/USDT", state_path, exchange=exchange)
    pos = b2.get_open_position()
    assert pos is not None
    assert pos.entry_price == 2000.0
