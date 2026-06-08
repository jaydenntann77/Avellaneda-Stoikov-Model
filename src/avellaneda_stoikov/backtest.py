"""Small backtesting helpers that connect the project modules.

This module starts with one-step backtesting only. A full historical loop over
many Binance order book events will be built later.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from avellaneda_stoikov.binance import (
    load_binance_depth_messages_jsonl,
    reconstruct_snapshots_from_binance_messages,
)
from avellaneda_stoikov.execution import (
    Fill,
    simulate_marketable_fills,
    simulate_next_snapshot_fills,
    simulate_next_snapshot_ladder_fills,
    simulate_touch_fills,
)
from avellaneda_stoikov.model import ModelParameters, Quote, generate_quote
from avellaneda_stoikov.order_book import OrderBookSnapshot
from avellaneda_stoikov.portfolio import PortfolioState, apply_fill_event, mark_to_market


FillModel = Literal["marketable", "touch", "next_snapshot"]


@dataclass(frozen=True)
class BacktestStepResult:
    """Result of applying the strategy to one order book snapshot."""

    mid_price: float
    market_spread: float
    book_bids: tuple[tuple[float, float], ...]
    book_asks: tuple[tuple[float, float], ...]
    quote: Quote
    fills: tuple[Fill, ...]
    portfolio: PortfolioState
    equity: float
    quote_levels: tuple[Quote, ...] = ()


@dataclass(frozen=True)
class BacktestSummary:
    """Compact metrics computed from completed backtest steps."""

    final_equity: float
    final_inventory: float
    total_fills: int
    buy_fills: int
    sell_fills: int
    traded_notional: float
    total_fees: float
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
    fill_model: FillModel = "marketable",
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
    _validate_fill_model(fill_model)

    quote = generate_quote(
        mid_price=snapshot.mid_price,
        inventory=portfolio.inventory,
        params=params,
    )
    fills = _simulate_fills(
        fill_model=fill_model,
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
        mid_price=snapshot.mid_price,
        market_spread=snapshot.spread,
        book_bids=_top_book_levels(snapshot.bids),
        book_asks=_top_book_levels(snapshot.asks),
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
    fill_model: FillModel = "marketable",
    quote_levels: int = 1,
    quote_level_spacing: float = 0.0,
) -> tuple[BacktestStepResult, ...]:
    """Run the simple strategy over a sequence of order book snapshots."""

    if not snapshots:
        raise ValueError("at least one snapshot is required.")
    _validate_fill_model(fill_model)
    _validate_quote_ladder(quote_levels=quote_levels, quote_level_spacing=quote_level_spacing)

    results: list[BacktestStepResult] = []
    portfolio = initial_portfolio

    for index, snapshot in enumerate(snapshots):
        if fill_model == "next_snapshot":
            next_snapshot = snapshots[index + 1] if index + 1 < len(snapshots) else None
            result = _run_next_snapshot_backtest_step(
                snapshot=snapshot,
                next_snapshot=next_snapshot,
                portfolio=portfolio,
                params=params,
                quote_quantity=quote_quantity,
                fee_rate=fee_rate,
                max_absolute_inventory=max_absolute_inventory,
                quote_levels=quote_levels,
                quote_level_spacing=quote_level_spacing,
            )
        else:
            result = run_backtest_step(
                snapshot=snapshot,
                portfolio=portfolio,
                params=params,
                quote_quantity=quote_quantity,
                fee_rate=fee_rate,
                max_absolute_inventory=max_absolute_inventory,
                fill_model=fill_model,
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
    fill_model: FillModel = "marketable",
    quote_levels: int = 1,
    quote_level_spacing: float = 0.0,
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
        fill_model=fill_model,
        quote_levels=quote_levels,
        quote_level_spacing=quote_level_spacing,
    )


def run_backtest_on_binance_jsonl(
    path: str | Path,
    initial_portfolio: PortfolioState,
    params: ModelParameters,
    quote_quantity: float,
    fee_rate: float = 0.0,
    max_absolute_inventory: float | None = None,
    fill_model: FillModel = "marketable",
    quote_levels: int = 1,
    quote_level_spacing: float = 0.0,
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
        fill_model=fill_model,
        quote_levels=quote_levels,
        quote_level_spacing=quote_level_spacing,
    )


def summarize_backtest(results: Sequence[BacktestStepResult]) -> BacktestSummary:
    """Return basic metrics from a completed backtest."""

    if not results:
        raise ValueError("at least one backtest result is required.")

    final_result = results[-1]
    fills = [fill for result in results for fill in result.fills]
    total_fills = len(fills)
    buy_fills = sum(1 for fill in fills if fill.side == "buy")
    sell_fills = sum(1 for fill in fills if fill.side == "sell")
    max_absolute_inventory = max(abs(result.portfolio.inventory) for result in results)
    equity_values = [result.equity for result in results]

    return BacktestSummary(
        final_equity=final_result.equity,
        final_inventory=final_result.portfolio.inventory,
        total_fills=total_fills,
        buy_fills=buy_fills,
        sell_fills=sell_fills,
        traded_notional=sum(fill.notional for fill in fills),
        total_fees=final_result.portfolio.fees_paid,
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


def _run_next_snapshot_backtest_step(
    snapshot: OrderBookSnapshot,
    next_snapshot: OrderBookSnapshot | None,
    portfolio: PortfolioState,
    params: ModelParameters,
    quote_quantity: float,
    fee_rate: float,
    max_absolute_inventory: float | None,
    quote_levels: int,
    quote_level_spacing: float,
) -> BacktestStepResult:
    if quote_quantity <= 0:
        raise ValueError("quote_quantity must be positive.")
    if fee_rate < 0:
        raise ValueError("fee_rate cannot be negative.")
    if max_absolute_inventory is not None and max_absolute_inventory <= 0:
        raise ValueError("max_absolute_inventory must be positive.")
    _validate_quote_ladder(quote_levels=quote_levels, quote_level_spacing=quote_level_spacing)

    quote = generate_quote(
        mid_price=snapshot.mid_price,
        inventory=portfolio.inventory,
        params=params,
    )
    if next_snapshot is None:
        fills = ()
    elif quote_levels == 1:
        fills = simulate_next_snapshot_fills(
            quote=quote,
            next_snapshot=next_snapshot,
            quantity=quote_quantity,
        )
    else:
        fills = simulate_next_snapshot_ladder_fills(
            quote=quote,
            next_snapshot=next_snapshot,
            quantity=quote_quantity,
            quote_levels=quote_levels,
            level_spacing=quote_level_spacing,
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

    mark_snapshot = next_snapshot or snapshot
    equity = mark_to_market(next_portfolio, mid_price=mark_snapshot.mid_price)
    return BacktestStepResult(
        mid_price=snapshot.mid_price,
        market_spread=snapshot.spread,
        book_bids=_top_book_levels(snapshot.bids),
        book_asks=_top_book_levels(snapshot.asks),
        quote=quote,
        fills=tuple(accepted_fills),
        portfolio=next_portfolio,
        equity=equity,
        quote_levels=_build_quote_ladder(quote, quote_levels, quote_level_spacing),
    )


def _simulate_fills(
    fill_model: FillModel,
    quote: Quote,
    snapshot: OrderBookSnapshot,
    quantity: float,
) -> tuple[Fill, ...]:
    if fill_model == "marketable":
        return simulate_marketable_fills(quote=quote, snapshot=snapshot, quantity=quantity)
    if fill_model == "touch":
        return simulate_touch_fills(quote=quote, snapshot=snapshot, quantity=quantity)
    raise ValueError('fill_model must be "marketable", "touch", or "next_snapshot".')


def _top_book_levels(levels, depth: int = 8) -> tuple[tuple[float, float], ...]:
    return tuple((level.price, level.quantity) for level in levels[:depth])


def _build_quote_ladder(
    quote: Quote,
    quote_levels: int,
    quote_level_spacing: float,
) -> tuple[Quote, ...]:
    return tuple(
        Quote(
            bid=quote.bid - level * quote_level_spacing,
            ask=quote.ask + level * quote_level_spacing,
            reservation_price=quote.reservation_price,
            spread=quote.spread + 2 * level * quote_level_spacing,
        )
        for level in range(quote_levels)
    )


def _validate_quote_ladder(quote_levels: int, quote_level_spacing: float) -> None:
    if quote_levels <= 0:
        raise ValueError("quote_levels must be positive.")
    if quote_level_spacing < 0:
        raise ValueError("quote_level_spacing cannot be negative.")


def _validate_fill_model(fill_model: FillModel) -> None:
    if fill_model not in {"marketable", "touch", "next_snapshot"}:
        raise ValueError('fill_model must be "marketable", "touch", or "next_snapshot".')


def _max_drawdown(equity_values: Sequence[float]) -> float:
    peak = equity_values[0]
    max_drawdown = 0.0

    for equity in equity_values:
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return max_drawdown
