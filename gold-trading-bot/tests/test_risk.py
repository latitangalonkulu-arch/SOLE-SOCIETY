from gold_bot.config import RiskConfig
from gold_bot.risk import RiskManager


def make_risk(**overrides) -> RiskManager:
    defaults = dict(risk_per_trade=0.01, max_open_positions=1, max_daily_loss_pct=0.03)
    defaults.update(overrides)
    return RiskManager(RiskConfig(**defaults))


def test_sizes_position_to_risk_fraction_of_equity():
    risk = make_risk(risk_per_trade=0.02)
    result = risk.size_position(equity=10000, entry_price=2000, stop_loss=1990, open_position_count=0)
    assert result.allowed
    # risk_amount = 200, stop_distance = 10 -> units = 20
    assert result.units == 20


def test_rejects_when_max_open_positions_reached():
    risk = make_risk(max_open_positions=1)
    result = risk.size_position(equity=10000, entry_price=2000, stop_loss=1990, open_position_count=1)
    assert not result.allowed
    assert "max_open_positions" in result.reason


def test_rejects_invalid_zero_stop_distance():
    risk = make_risk()
    result = risk.size_position(equity=10000, entry_price=2000, stop_loss=2000, open_position_count=0)
    assert not result.allowed


def test_daily_loss_limit_blocks_new_trades():
    risk = make_risk(max_daily_loss_pct=0.03)
    # Prime the day's starting equity.
    risk.daily_loss_limit_hit(equity=10000)
    # Lose more than 3% intraday.
    result = risk.size_position(equity=9600, entry_price=2000, stop_loss=1990, open_position_count=0)
    assert not result.allowed
    assert "daily loss" in result.reason
