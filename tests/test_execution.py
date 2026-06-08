import pytest

from avellaneda_stoikov.execution import Fill


def test_fill_stores_side_price_quantity_and_notional() -> None:
    fill = Fill(side="buy", price=100.0, quantity=2.0)

    assert fill.side == "buy"
    assert fill.price == pytest.approx(100.0)
    assert fill.quantity == pytest.approx(2.0)
    assert fill.notional == pytest.approx(200.0)


def test_fill_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match='side must be either "buy" or "sell"'):
        Fill(side="hold", price=100.0, quantity=1.0)

    with pytest.raises(ValueError, match="price must be positive"):
        Fill(side="buy", price=0.0, quantity=1.0)

    with pytest.raises(ValueError, match="quantity must be positive"):
        Fill(side="buy", price=100.0, quantity=0.0)
