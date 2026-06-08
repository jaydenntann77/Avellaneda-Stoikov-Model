"""Execution data structures for simulated market making fills.

This module describes fills after they happen in a backtest. It does not decide
whether a quote should be filled; fill models will come later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from avellaneda_stoikov.model import Quote
from avellaneda_stoikov.order_book import OrderBookSnapshot


FillSide = Literal["buy", "sell"]


@dataclass(frozen=True)
class Fill:
    """One simulated fill received by the market maker."""

    side: FillSide
    price: float
    quantity: float

    def __post_init__(self) -> None:
        if self.side not in {"buy", "sell"}:
            raise ValueError('side must be either "buy" or "sell".')
        if self.price <= 0:
            raise ValueError("price must be positive.")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive.")

    @property
    def notional(self) -> float:
        """Trade value before fees."""

        return self.price * self.quantity


def simulate_marketable_fills(
    quote: Quote,
    snapshot: OrderBookSnapshot,
    quantity: float,
) -> tuple[Fill, ...]:
    """Return fills for quotes that immediately cross the top of book.

    This is a deliberately simple execution rule. It only fills quotes that are
    marketable against the visible best bid or ask in the current snapshot.
    """

    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    fills: list[Fill] = []

    if quote.bid >= snapshot.best_ask:
        fills.append(Fill(side="buy", price=snapshot.best_ask, quantity=quantity))

    if quote.ask <= snapshot.best_bid:
        fills.append(Fill(side="sell", price=snapshot.best_bid, quantity=quantity))

    return tuple(fills)


def simulate_touch_fills(
    quote: Quote,
    snapshot: OrderBookSnapshot,
    quantity: float,
) -> tuple[Fill, ...]:
    """Return fills for quotes placed at or through the current best prices.

    This approximates passive execution at the top of book. If our bid is at
    least the current best bid, we assume the bid can buy. If our ask is no
    higher than the current best ask, we assume the ask can sell.
    """

    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    fills: list[Fill] = []

    if quote.bid >= snapshot.best_bid:
        fills.append(Fill(side="buy", price=quote.bid, quantity=quantity))

    if quote.ask <= snapshot.best_ask:
        fills.append(Fill(side="sell", price=quote.ask, quantity=quantity))

    return tuple(fills)


def simulate_next_snapshot_fills(
    quote: Quote,
    next_snapshot: OrderBookSnapshot,
    quantity: float,
) -> tuple[Fill, ...]:
    """Return fills when the next book snapshot moves through our quotes.

    This is a simple passive-fill approximation. A bid fills if the next best
    ask is at or below our bid. An ask fills if the next best bid is at or above
    our ask.
    """

    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    fills: list[Fill] = []

    if next_snapshot.best_ask <= quote.bid:
        fills.append(Fill(side="buy", price=quote.bid, quantity=quantity))

    if next_snapshot.best_bid >= quote.ask:
        fills.append(Fill(side="sell", price=quote.ask, quantity=quantity))

    return tuple(fills)


def simulate_next_snapshot_ladder_fills(
    quote: Quote,
    next_snapshot: OrderBookSnapshot,
    quantity: float,
    quote_levels: int,
    level_spacing: float,
) -> tuple[Fill, ...]:
    """Return passive fills for a symmetric ladder around an A-S quote.

    The first level is the model's base bid/ask. Additional levels are placed
    farther from the reservation price by ``level_spacing``. This increases the
    number of passive quote opportunities without changing the A-S quote center.
    """

    if quantity <= 0:
        raise ValueError("quantity must be positive.")
    if quote_levels <= 0:
        raise ValueError("quote_levels must be positive.")
    if level_spacing < 0:
        raise ValueError("level_spacing cannot be negative.")

    fills: list[Fill] = []
    for level in range(quote_levels):
        bid = quote.bid - level * level_spacing
        ask = quote.ask + level * level_spacing
        if next_snapshot.best_ask <= bid:
            fills.append(Fill(side="buy", price=bid, quantity=quantity))
        if next_snapshot.best_bid >= ask:
            fills.append(Fill(side="sell", price=ask, quantity=quantity))

    return tuple(fills)
