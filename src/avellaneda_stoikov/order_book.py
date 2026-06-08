"""Small order book helpers for L2 market data snapshots.

This module does not download or parse Binance data yet. It only defines the
clean shape we want parsed order book data to have before a backtest uses it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class BookLevel:
    """One price level in the order book."""

    price: float
    quantity: float


@dataclass(frozen=True)
class OrderBookSnapshot:
    """Validated bid/ask levels observed at one point in time."""

    bids: tuple[BookLevel, ...] # each side is a tuple of BookLevels 
    asks: tuple[BookLevel, ...]

    @classmethod
    def from_levels(
        cls,
        bids: Sequence[tuple[float, float]],
        asks: Sequence[tuple[float, float]],
    ) -> "OrderBookSnapshot":
        """Create a snapshot from raw (price, quantity) pairs.

        Bids are sorted from highest to lowest price. Asks are sorted from
        lowest to highest price. This makes the best bid and best ask live at
        index 0, which is exactly what the model needs for mid-price input.
        """

        bid_levels = tuple(BookLevel(price=price, quantity=quantity) for price, quantity in bids)
        ask_levels = tuple(BookLevel(price=price, quantity=quantity) for price, quantity in asks)
        _validate_levels(bid_levels, side_name="bids")
        _validate_levels(ask_levels, side_name="asks")

        sorted_bids = tuple(sorted(bid_levels, key=lambda level: level.price, reverse=True))
        sorted_asks = tuple(sorted(ask_levels, key=lambda level: level.price))
        snapshot = cls(bids=sorted_bids, asks=sorted_asks)
        snapshot._validate_crossed_book()
        return snapshot

    @property
    def best_bid(self) -> float:
        """Highest bid price in the snapshot."""

        return self.bids[0].price

    @property
    def best_ask(self) -> float:
        """Lowest ask price in the snapshot."""

        return self.asks[0].price

    @property
    def mid_price(self) -> float:
        """Mid-price computed from the best bid and best ask."""

        return (self.best_bid + self.best_ask) / 2.0

    @property
    def spread(self) -> float:
        """Top-of-book spread."""

        return self.best_ask - self.best_bid

    def _validate_crossed_book(self) -> None:
        if self.best_bid >= self.best_ask:
            raise ValueError("best bid must be lower than best ask.")


def _validate_levels(levels: tuple[BookLevel, ...], side_name: str) -> None:
    if not levels:
        raise ValueError(f"{side_name} must contain at least one level.")
    if any(level.price <= 0 for level in levels):
        raise ValueError(f"{side_name} prices must be positive.")
    if any(level.quantity <= 0 for level in levels):
        raise ValueError(f"{side_name} quantities must be positive.")
