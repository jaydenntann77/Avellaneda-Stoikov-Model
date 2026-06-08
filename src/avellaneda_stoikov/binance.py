"""Helpers for converting Binance-style order book data into project objects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from avellaneda_stoikov.order_book import OrderBookSnapshot


@dataclass(frozen=True)
class BinanceOrderBook:
    """Local order book state built from Binance depth levels."""

    bids: Mapping[float, float]
    asks: Mapping[float, float]

    @classmethod
    def from_depth_message(cls, message: Mapping[str, Any]) -> "BinanceOrderBook":
        """Create local book state from a Binance-style depth message."""

        bids = _parse_price_quantity_levels(
            _get_levels(message, long_key="bids", short_key="b"),
            side_name="bids",
        )
        asks = _parse_price_quantity_levels(
            _get_levels(message, long_key="asks", short_key="a"),
            side_name="asks",
        )
        return cls(
            bids=dict(bids),
            asks=dict(asks),
        )

    def apply_depth_update(self, message: Mapping[str, Any]) -> "BinanceOrderBook":
        """Return new book state after applying Binance depth update levels.

        Binance update quantities are absolute quantities at a price level.
        Quantity 0 means the level should be removed.
        """

        if not _has_bid_or_ask_levels(message):
            raise ValueError("depth update must contain bid or ask levels.")

        next_bids = dict(self.bids)
        next_asks = dict(self.asks)
        if "b" in message or "bids" in message:
            _apply_level_updates(
                levels=next_bids,
                updates=_parse_price_quantity_levels(
                    _get_levels(message, long_key="bids", short_key="b"),
                    side_name="bids",
                ),
            )
        if "a" in message or "asks" in message:
            _apply_level_updates(
                levels=next_asks,
                updates=_parse_price_quantity_levels(
                    _get_levels(message, long_key="asks", short_key="a"),
                    side_name="asks",
                ),
            )

        return BinanceOrderBook(bids=next_bids, asks=next_asks)

    def to_snapshot(self) -> OrderBookSnapshot:
        """Convert local book state to the project snapshot object."""

        return OrderBookSnapshot.from_levels(
            bids=tuple(self.bids.items()),
            asks=tuple(self.asks.items()),
        )


def reconstruct_snapshots_from_binance_messages(
    messages: Sequence[Mapping[str, Any]],
) -> tuple[OrderBookSnapshot, ...]:
    """Reconstruct snapshots from one full depth message and later updates.

    The first message is treated as the initial full book. Each later message is
    applied as a Binance depth update, and one OrderBookSnapshot is emitted
    after every message.
    """

    if not messages:
        raise ValueError("at least one Binance depth message is required.")

    book = BinanceOrderBook.from_depth_message(messages[0])
    snapshots = [book.to_snapshot()]

    for message in messages[1:]:
        book = book.apply_depth_update(message)
        snapshots.append(book.to_snapshot())

    return tuple(snapshots)


def snapshot_from_binance_depth(message: Mapping[str, Any]) -> OrderBookSnapshot:
    """Create an OrderBookSnapshot from a Binance-style depth message.

    Binance data commonly represents price levels as strings, for example:

        ["100000.0", "0.5"]

    This helper converts those raw levels into floats, then delegates sorting
    and validation to OrderBookSnapshot.
    """

    bids = _get_levels(message, long_key="bids", short_key="b")
    asks = _get_levels(message, long_key="asks", short_key="a")
    return OrderBookSnapshot.from_levels(
        bids=_parse_price_quantity_levels(bids, side_name="bids"),
        asks=_parse_price_quantity_levels(asks, side_name="asks"),
    )


def _get_levels(
    message: Mapping[str, Any],
    long_key: str,
    short_key: str,
) -> Any:
    if long_key in message:
        return message[long_key]
    if short_key in message:
        return message[short_key]
    raise ValueError(f"message must contain {long_key!r} or {short_key!r}.")


def _has_bid_or_ask_levels(message: Mapping[str, Any]) -> bool:
    return any(key in message for key in ("bids", "b", "asks", "a"))


def _parse_price_quantity_levels(
    raw_levels: Any,
    side_name: str,
) -> tuple[tuple[float, float], ...]:
    if not isinstance(raw_levels, Sequence) or isinstance(raw_levels, str):
        raise ValueError(f"{side_name} must be a sequence of price/quantity levels.")

    parsed_levels = []
    for raw_level in raw_levels:
        if not isinstance(raw_level, Sequence) or isinstance(raw_level, str):
            raise ValueError(f"each {side_name} level must be a price/quantity pair.")
        if len(raw_level) != 2:
            raise ValueError(f"each {side_name} level must contain exactly two values.")

        price, quantity = raw_level
        try:
            parsed_levels.append((float(price), float(quantity)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{side_name} levels must contain numeric values.") from exc

    return tuple(parsed_levels)


def _apply_level_updates(
    levels: dict[float, float],
    updates: tuple[tuple[float, float], ...],
) -> None:
    for price, quantity in updates:
        if quantity == 0:
            levels.pop(price, None)
        else:
            levels[price] = quantity
