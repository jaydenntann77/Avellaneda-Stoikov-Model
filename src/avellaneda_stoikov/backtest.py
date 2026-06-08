"""Small backtesting helpers that connect the project modules.

This module starts with one-step backtesting only. A full historical loop over
many Binance order book events will be built later.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avellaneda_stoikov.binance import (
    load_binance_depth_messages_jsonl,
    reconstruct_snapshots_from_binance_messages,
)
from avellaneda_stoikov.execution import Fill, simulate_marketable_fills
from avellaneda_stoikov.model import ModelParameters, Quote, generate_quote
from avellaneda_stoikov.order_book import OrderBookSnapshot
from avellaneda_stoikov.portfolio import PortfolioState, apply_fill_event, mark_to_market


@dataclass(frozen=True)
class BacktestStepResult:
    """Result of applying the strategy to one order book snapshot."""

    quote: Quote
    fills: tuple[Fill, ...]
    portfolio: PortfolioState
    equity: float


@dataclass(frozen=True)
class BacktestSummary:
    """Compact metrics computed from completed backtest steps."""

    final_equity: float
    final_inventory: float
    total_fills: int
    max_absolute_inventory: float
    min_equity: float
    max_equity: float
    max_drawdown: float


def run_backtest_step(
    snapshot: OrderBookSnapshot,
    portfolio: PortfolioState,
    params: ModelParameters,
    quote_quantity: float,
    fee_rate: float = 0.0,
    max_absolute_inventory: float | None = None,
) -> BacktestStepResult:
    """Run one simple quote/fill/accounting step.

    The step uses current inventory to generate an A-S quote, simulates only
    immediately marketable fills, applies those fills to the portfolio, then
    marks the result to the snapshot mid-price.
    """

    if quote_quantity <= 0:
        raise ValueError("quote_quantity must be positive.")
    if fee_rate < 0:
        raise ValueError("fee_rate cannot be negative.")
    if max_absolute_inventory is not None and max_absolute_inventory <= 0:
        raise ValueError("max_absolute_inventory must be positive.")

    quote = generate_quote(
        mid_price=snapshot.mid_price,
        inventory=portfolio.inventory,
        params=params,
    )
    fills = simulate_marketable_fills(
        quote=quote,
        snapshot=snapshot,
        quantity=quote_quantity,
    )

    next_portfolio = portfolio
    accepted_fills: list[Fill] = []
    for fill in fills:
        if not _fill_respects_inventory_limit(
            portfolio=next_portfolio,
            fill=fill,
            max_absolute_inventory=max_absolute_inventory,
        ):
            continue
        next_portfolio = apply_fill_event(
            state=next_portfolio,
            fill=fill,
            fee_rate=fee_rate,
        )
        accepted_fills.append(fill)

    equity = mark_to_market(next_portfolio, mid_price=snapshot.mid_price)
    return BacktestStepResult(
        quote=quote,
        fills=tuple(accepted_fills),
        portfolio=next_portfolio,
        equity=equity,
    )


def run_backtest(
    snapshots: Sequence[OrderBookSnapshot],
    initial_portfolio: PortfolioState,
    params: ModelParameters,
    quote_quantity: float,
    fee_rate: float = 0.0,
    max_absolute_inventory: float | None = None,
) -> tuple[BacktestStepResult, ...]:
    """Run the simple strategy over a sequence of order book snapshots."""

    if not snapshots:
        raise ValueError("at least one snapshot is required.")

    results: list[BacktestStepResult] = []
    portfolio = initial_portfolio

    for snapshot in snapshots:
        result = run_backtest_step(
            snapshot=snapshot,
            portfolio=portfolio,
            params=params,
            quote_quantity=quote_quantity,
            fee_rate=fee_rate,
            max_absolute_inventory=max_absolute_inventory,
        )
        results.append(result)
        portfolio = result.portfolio

    return tuple(results)


def run_backtest_on_binance_messages(
    messages: Sequence[dict[str, Any]],
    initial_portfolio: PortfolioState,
    params: ModelParameters,
    quote_quantity: float,
    fee_rate: float = 0.0,
    max_absolute_inventory: float | None = None,
) -> tuple[BacktestStepResult, ...]:
    """Reconstruct Binance snapshots, then run the simple backtest."""

    snapshots = reconstruct_snapshots_from_binance_messages(messages)
    return run_backtest(
        snapshots=snapshots,
        initial_portfolio=initial_portfolio,
        params=params,
        quote_quantity=quote_quantity,
        fee_rate=fee_rate,
        max_absolute_inventory=max_absolute_inventory,
    )


def run_backtest_on_binance_jsonl(
    path: str | Path,
    initial_portfolio: PortfolioState,
    params: ModelParameters,
    quote_quantity: float,
    fee_rate: float = 0.0,
    max_absolute_inventory: float | None = None,
) -> tuple[BacktestStepResult, ...]:
    """Load Binance JSONL messages, reconstruct snapshots, then run a backtest."""

    messages = load_binance_depth_messages_jsonl(path)
    return run_backtest_on_binance_messages(
        messages=messages,
        initial_portfolio=initial_portfolio,
        params=params,
        quote_quantity=quote_quantity,
        fee_rate=fee_rate,
        max_absolute_inventory=max_absolute_inventory,
    )


def summarize_backtest(results: Sequence[BacktestStepResult]) -> BacktestSummary:
    """Return basic metrics from a completed backtest."""

    if not results:
        raise ValueError("at least one backtest result is required.")

    final_result = results[-1]
    total_fills = sum(len(result.fills) for result in results)
    max_absolute_inventory = max(abs(result.portfolio.inventory) for result in results)
    equity_values = [result.equity for result in results]

    return BacktestSummary(
        final_equity=final_result.equity,
        final_inventory=final_result.portfolio.inventory,
        total_fills=total_fills,
        max_absolute_inventory=max_absolute_inventory,
        min_equity=min(equity_values),
        max_equity=max(equity_values),
        max_drawdown=_max_drawdown(equity_values),
    )


def _fill_respects_inventory_limit(
    portfolio: PortfolioState,
    fill: Fill,
    max_absolute_inventory: float | None,
) -> bool:
    if max_absolute_inventory is None:
        return True

    inventory_change = fill.quantity if fill.side == "buy" else -fill.quantity
    next_inventory = portfolio.inventory + inventory_change
    return abs(next_inventory) <= max_absolute_inventory


def _max_drawdown(equity_values: Sequence[float]) -> float:
    peak = equity_values[0]
    max_drawdown = 0.0

    for equity in equity_values:
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return max_drawdown
