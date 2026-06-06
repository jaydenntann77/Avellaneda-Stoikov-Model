import pytest

from avellaneda_stoikov.order_book import OrderBookSnapshot


def test_snapshot_sorts_levels_for_top_of_book_access() -> None:
    snapshot = OrderBookSnapshot.from_levels(
        bids=[(99.0, 2.0), (100.0, 1.0)],
        asks=[(102.0, 1.5), (101.0, 3.0)],
    )

    assert snapshot.best_bid == pytest.approx(100.0)
    assert snapshot.best_ask == pytest.approx(101.0)


def test_snapshot_computes_mid_price_and_spread() -> None:
    snapshot = OrderBookSnapshot.from_levels(
        bids=[(100.0, 1.0)],
        asks=[(102.0, 1.0)],
    )

    assert snapshot.mid_price == pytest.approx(101.0)
    assert snapshot.spread == pytest.approx(2.0)


def test_snapshot_rejects_empty_sides() -> None:
    with pytest.raises(ValueError, match="bids must contain at least one level"):
        OrderBookSnapshot.from_levels(bids=[], asks=[(101.0, 1.0)])

    with pytest.raises(ValueError, match="asks must contain at least one level"):
        OrderBookSnapshot.from_levels(bids=[(100.0, 1.0)], asks=[])


def test_snapshot_rejects_non_positive_prices_and_quantities() -> None:
    with pytest.raises(ValueError, match="bids prices must be positive"):
        OrderBookSnapshot.from_levels(bids=[(0.0, 1.0)], asks=[(101.0, 1.0)])

    with pytest.raises(ValueError, match="asks quantities must be positive"):
        OrderBookSnapshot.from_levels(bids=[(100.0, 1.0)], asks=[(101.0, 0.0)])


def test_snapshot_rejects_crossed_or_locked_books() -> None:
    with pytest.raises(ValueError, match="best bid must be lower than best ask"):
        OrderBookSnapshot.from_levels(bids=[(101.0, 1.0)], asks=[(101.0, 1.0)])

    with pytest.raises(ValueError, match="best bid must be lower than best ask"):
        OrderBookSnapshot.from_levels(bids=[(102.0, 1.0)], asks=[(101.0, 1.0)])
