from pathlib import Path

import pytest

from gold_bot.broker.paper import PaperBroker


@pytest.fixture
def broker(tmp_path: Path) -> PaperBroker:
    return PaperBroker(starting_balance=10000.0, state_path=tmp_path / "state.json")


def test_open_and_close_long_position_realizes_pnl(broker: PaperBroker):
    broker.open_position("long", units=10, price=2000, stop_loss=1990, take_profit=2030)
    assert broker.get_open_position() is not None

    trade = broker.close_position(price=2020, reason="manual close")
    assert trade.pnl == pytest.approx(200.0)
    assert broker.get_equity() == pytest.approx(10200.0)
    assert broker.get_open_position() is None


def test_short_position_profits_when_price_falls(broker: PaperBroker):
    broker.open_position("short", units=5, price=2000, stop_loss=2010, take_profit=1980)
    trade = broker.close_position(price=1980, reason="take_profit hit")
    assert trade.pnl == pytest.approx(100.0)


def test_check_stop_take_closes_long_on_stop_loss(broker: PaperBroker):
    broker.open_position("long", units=10, price=2000, stop_loss=1990, take_profit=2030)
    trade = broker.check_stop_take(current_price=1985)
    assert trade is not None
    assert trade.exit_price == 1990
    assert trade.pnl == pytest.approx((1990 - 2000) * 10)
    assert broker.get_open_position() is None


def test_check_stop_take_does_nothing_when_price_between_sl_tp(broker: PaperBroker):
    broker.open_position("long", units=10, price=2000, stop_loss=1990, take_profit=2030)
    trade = broker.check_stop_take(current_price=2005)
    assert trade is None
    assert broker.get_open_position() is not None


def test_cannot_open_second_position_while_one_is_open(broker: PaperBroker):
    broker.open_position("long", units=10, price=2000, stop_loss=1990, take_profit=2030)
    with pytest.raises(RuntimeError):
        broker.open_position("long", units=5, price=2010, stop_loss=2000, take_profit=2040)


def test_state_persists_across_instances(tmp_path: Path):
    state_path = tmp_path / "state.json"
    b1 = PaperBroker(starting_balance=10000.0, state_path=state_path)
    b1.open_position("long", units=10, price=2000, stop_loss=1990, take_profit=2030)

    b2 = PaperBroker(starting_balance=10000.0, state_path=state_path)
    pos = b2.get_open_position()
    assert pos is not None
    assert pos.entry_price == 2000
