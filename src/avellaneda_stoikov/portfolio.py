"""Portfolio accounting helpers for market making backtests.

This module tracks cash and inventory after simulated fills. It intentionally
does not decide whether a quote gets filled; execution logic will come later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FillSide = Literal["buy", "sell"]


@dataclass(frozen=True)
class PortfolioState:
    """Cash and inventory held by the simulated market maker."""

    cash: float = 0.0
    inventory: float = 0.0


def apply_fill(
    state: PortfolioState,
    side: FillSide,
    price: float,
    quantity: float,
    fee_rate: float = 0.0,
) -> PortfolioState:
    """Return the portfolio state after one simulated fill.

    Args:
        state: Current portfolio state.
        side: "buy" if our bid was filled, or "sell" if our ask was filled.
        price: Fill price.
        quantity: Filled quantity.
        fee_rate: Proportional trading fee. For example, 0.0004 means 4 bps.
    """

    _validate_fill_inputs(side=side, price=price, quantity=quantity, fee_rate=fee_rate)

    notional = price * quantity
    fee = notional * fee_rate

    if side == "buy":
        return PortfolioState(
            cash=state.cash - notional - fee,
            inventory=state.inventory + quantity,
        )

    return PortfolioState(
        cash=state.cash + notional - fee,
        inventory=state.inventory - quantity,
    )


def mark_to_market(state: PortfolioState, mid_price: float) -> float:
    """Return portfolio equity using the current mid-price."""

    if mid_price <= 0:
        raise ValueError("mid_price must be positive.")

    return state.cash + state.inventory * mid_price


def _validate_fill_inputs(
    side: FillSide,
    price: float,
    quantity: float,
    fee_rate: float,
) -> None:
    if side not in {"buy", "sell"}:
        raise ValueError('side must be either "buy" or "sell".')
    if price <= 0:
        raise ValueError("price must be positive.")
    if quantity <= 0:
        raise ValueError("quantity must be positive.")
    if fee_rate < 0:
        raise ValueError("fee_rate cannot be negative.")
