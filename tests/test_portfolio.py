import pytest

from avellaneda_stoikov.execution import Fill
from avellaneda_stoikov.portfolio import PortfolioState, apply_fill, apply_fill_event, mark_to_market


def test_buy_fill_reduces_cash_and_increases_inventory() -> None:
    state = PortfolioState()

    next_state = apply_fill(state, side="buy", price=100.0, quantity=2.0)

    assert next_state.cash == pytest.approx(-200.0)
    assert next_state.inventory == pytest.approx(2.0)
    assert next_state.fees_paid == pytest.approx(0.0)


def test_sell_fill_increases_cash_and_decreases_inventory() -> None:
    state = PortfolioState(inventory=2.0)

    next_state = apply_fill(state, side="sell", price=101.0, quantity=1.5)

    assert next_state.cash == pytest.approx(151.5)
    assert next_state.inventory == pytest.approx(0.5)
    assert next_state.fees_paid == pytest.approx(0.0)


def test_fee_is_paid_on_both_buys_and_sells() -> None:
    buy_state = apply_fill(
        PortfolioState(),
        side="buy",
        price=100.0,
        quantity=1.0,
        fee_rate=0.001,
    )
    sell_state = apply_fill(
        PortfolioState(),
        side="sell",
        price=100.0,
        quantity=1.0,
        fee_rate=0.001,
    )

    assert buy_state.cash == pytest.approx(-100.1)
    assert sell_state.cash == pytest.approx(99.9)
    assert buy_state.fees_paid == pytest.approx(0.1)
    assert sell_state.fees_paid == pytest.approx(0.1)


def test_fees_accumulate_across_fills() -> None:
    state = PortfolioState()
    state = apply_fill(state, side="buy", price=100.0, quantity=1.0, fee_rate=0.001)
    state = apply_fill(state, side="sell", price=101.0, quantity=1.0, fee_rate=0.001)

    assert state.fees_paid == pytest.approx(0.201)


def test_mark_to_market_values_inventory_at_mid_price() -> None:
    state = PortfolioState(cash=-200.0, inventory=2.0)

    equity = mark_to_market(state, mid_price=101.0)

    assert equity == pytest.approx(2.0)


def test_apply_fill_event_updates_portfolio_from_fill_object() -> None:
    fill = Fill(side="buy", price=100.0, quantity=2.0)

    next_state = apply_fill_event(PortfolioState(), fill=fill)

    assert next_state.cash == pytest.approx(-200.0)
    assert next_state.inventory == pytest.approx(2.0)
    assert next_state.fees_paid == pytest.approx(0.0)


def test_invalid_fill_inputs_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match='side must be either "buy" or "sell"'):
        apply_fill(PortfolioState(), side="hold", price=100.0, quantity=1.0)

    with pytest.raises(ValueError, match="price must be positive"):
        apply_fill(PortfolioState(), side="buy", price=0.0, quantity=1.0)

    with pytest.raises(ValueError, match="quantity must be positive"):
        apply_fill(PortfolioState(), side="buy", price=100.0, quantity=0.0)

    with pytest.raises(ValueError, match="fee_rate cannot be negative"):
        apply_fill(PortfolioState(), side="buy", price=100.0, quantity=1.0, fee_rate=-0.001)


def test_mark_to_market_requires_positive_mid_price() -> None:
    with pytest.raises(ValueError, match="mid_price must be positive"):
        mark_to_market(PortfolioState(), mid_price=0.0)
