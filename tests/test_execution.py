import pytest

from avellaneda_stoikov.execution import Fill, simulate_marketable_fills
from avellaneda_stoikov.model import Quote
from avellaneda_stoikov.order_book import OrderBookSnapshot


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


def test_non_marketable_quote_produces_no_fills() -> None:
    quote = Quote(bid=99.0, ask=101.0, reservation_price=100.0, spread=2.0)
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.5, 1.0)], asks=[(100.5, 1.0)])

    fills = simulate_marketable_fills(quote, snapshot, quantity=1.0)

    assert fills == ()


def test_marketable_bid_buys_at_best_ask() -> None:
    quote = Quote(bid=101.0, ask=102.0, reservation_price=101.5, spread=1.0)
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.5, 1.0)], asks=[(100.5, 1.0)])

    fills = simulate_marketable_fills(quote, snapshot, quantity=2.0)

    assert fills == (Fill(side="buy", price=100.5, quantity=2.0),)


def test_marketable_ask_sells_at_best_bid() -> None:
    quote = Quote(bid=98.0, ask=99.0, reservation_price=98.5, spread=1.0)
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.5, 1.0)], asks=[(100.5, 1.0)])

    fills = simulate_marketable_fills(quote, snapshot, quantity=2.0)

    assert fills == (Fill(side="sell", price=99.5, quantity=2.0),)


def test_marketable_fill_simulation_requires_positive_quantity() -> None:
    quote = Quote(bid=99.0, ask=101.0, reservation_price=100.0, spread=2.0)
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.5, 1.0)], asks=[(100.5, 1.0)])

    with pytest.raises(ValueError, match="quantity must be positive"):
        simulate_marketable_fills(quote, snapshot, quantity=0.0)
