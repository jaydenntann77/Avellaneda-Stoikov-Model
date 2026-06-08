"""Execution data structures for simulated market making fills.

This module describes fills after they happen in a backtest. It does not decide
whether a quote should be filled; fill models will come later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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
