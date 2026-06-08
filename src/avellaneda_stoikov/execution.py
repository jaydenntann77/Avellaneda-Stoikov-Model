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
