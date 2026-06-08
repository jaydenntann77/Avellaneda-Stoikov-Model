import pytest

from avellaneda_stoikov.binance import (
    BinanceOrderBook,
    reconstruct_snapshots_from_binance_messages,
    snapshot_from_binance_depth,
)


def test_snapshot_from_binance_depth_parses_rest_style_levels() -> None:
    message = {
        "bids": [["99.0", "2.0"], ["100.0", "1.0"]],
        "asks": [["102.0", "1.5"], ["101.0", "3.0"]],
    }

    snapshot = snapshot_from_binance_depth(message)

    assert snapshot.best_bid == pytest.approx(100.0)
    assert snapshot.best_ask == pytest.approx(101.0)
    assert snapshot.mid_price == pytest.approx(100.5)


def test_snapshot_from_binance_depth_parses_stream_style_levels() -> None:
    message = {
        "b": [["99.0", "2.0"], ["100.0", "1.0"]],
        "a": [["102.0", "1.5"], ["101.0", "3.0"]],
    }

    snapshot = snapshot_from_binance_depth(message)

    assert snapshot.best_bid == pytest.approx(100.0)
    assert snapshot.best_ask == pytest.approx(101.0)


def test_snapshot_from_binance_depth_rejects_missing_sides() -> None:
    with pytest.raises(ValueError, match="message must contain 'bids' or 'b'"):
        snapshot_from_binance_depth({"asks": [["101.0", "1.0"]]})

    with pytest.raises(ValueError, match="message must contain 'asks' or 'a'"):
        snapshot_from_binance_depth({"bids": [["100.0", "1.0"]]})


def test_snapshot_from_binance_depth_rejects_malformed_levels() -> None:
    with pytest.raises(ValueError, match="bids must be a sequence"):
        snapshot_from_binance_depth({"bids": "bad", "asks": [["101.0", "1.0"]]})

    with pytest.raises(ValueError, match="exactly two values"):
        snapshot_from_binance_depth({"bids": [["100.0"]], "asks": [["101.0", "1.0"]]})

    with pytest.raises(ValueError, match="numeric values"):
        snapshot_from_binance_depth({"bids": [["bad", "1.0"]], "asks": [["101.0", "1.0"]]})


def test_binance_order_book_applies_depth_update_levels() -> None:
    book = BinanceOrderBook.from_depth_message(
        {
            "bids": [["100.0", "1.0"], ["99.0", "2.0"]],
            "asks": [["101.0", "1.0"], ["102.0", "2.0"]],
        }
    )

    updated_book = book.apply_depth_update(
        {
            "b": [["100.0", "3.0"], ["98.0", "4.0"]],
            "a": [["101.0", "0.0"], ["103.0", "5.0"]],
        }
    )
    snapshot = updated_book.to_snapshot()

    assert updated_book.bids == {100.0: 3.0, 99.0: 2.0, 98.0: 4.0}
    assert updated_book.asks == {102.0: 2.0, 103.0: 5.0}
    assert snapshot.best_bid == pytest.approx(100.0)
    assert snapshot.best_ask == pytest.approx(102.0)


def test_binance_order_book_update_does_not_mutate_original_book() -> None:
    book = BinanceOrderBook.from_depth_message(
        {
            "bids": [["100.0", "1.0"]],
            "asks": [["101.0", "1.0"]],
        }
    )

    updated_book = book.apply_depth_update({"b": [["100.0", "2.0"]]})

    assert book.bids == {100.0: 1.0}
    assert updated_book.bids == {100.0: 2.0}


def test_reconstruct_snapshots_from_binance_messages_replays_updates() -> None:
    messages = [
        {
            "bids": [["100.0", "1.0"], ["99.0", "2.0"]],
            "asks": [["101.0", "1.0"], ["102.0", "2.0"]],
        },
        {
            "b": [["100.0", "0.0"], ["98.0", "3.0"]],
        },
        {
            "a": [["101.0", "0.0"], ["103.0", "4.0"]],
        },
    ]

    snapshots = reconstruct_snapshots_from_binance_messages(messages)

    assert len(snapshots) == 3
    assert snapshots[0].best_bid == pytest.approx(100.0)
    assert snapshots[1].best_bid == pytest.approx(99.0)
    assert snapshots[2].best_ask == pytest.approx(102.0)


def test_reconstruct_snapshots_from_binance_messages_rejects_empty_sequence() -> None:
    with pytest.raises(ValueError, match="at least one Binance depth message is required"):
        reconstruct_snapshots_from_binance_messages([])


def test_binance_order_book_rejects_update_without_bid_or_ask_levels() -> None:
    book = BinanceOrderBook.from_depth_message(
        {
            "bids": [["100.0", "1.0"]],
            "asks": [["101.0", "1.0"]],
        }
    )

    with pytest.raises(ValueError, match="depth update must contain bid or ask levels"):
        book.apply_depth_update({"eventTime": 123})
