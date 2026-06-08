"""Helpers for preparing backtest results for reports and demos."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from avellaneda_stoikov.backtest import BacktestStepResult, summarize_backtest


def backtest_summary_to_dict(
    results: Sequence[BacktestStepResult],
    initial_equity: float = 0.0,
) -> dict[str, float | int]:
    """Return summary metrics as a plain dictionary."""

    summary = asdict(summarize_backtest(results))
    summary["initial_equity"] = initial_equity
    summary["net_pnl"] = summary["final_equity"] - initial_equity
    return summary


def backtest_results_to_rows(results: Sequence[BacktestStepResult]) -> tuple[dict[str, Any], ...]:
    """Return one plain row per backtest step for tables or charts."""

    rows = []
    for index, result in enumerate(results, start=1):
        rows.append(
            {
                "step": index,
                "mid_price": result.mid_price,
                "market_spread": result.market_spread,
                "bid": result.quote.bid,
                "ask": result.quote.ask,
                "reservation_price": result.quote.reservation_price,
                "spread": result.quote.spread,
                "bid_distance_from_mid": result.mid_price - result.quote.bid,
                "ask_distance_from_mid": result.quote.ask - result.mid_price,
                "quote_levels": tuple(
                    {
                        "level": level,
                        "bid": quote.bid,
                        "ask": quote.ask,
                        "reservation_price": quote.reservation_price,
                        "spread": quote.spread,
                    }
                    for level, quote in enumerate(result.quote_levels or (result.quote,), start=1)
                ),
                "fills": len(result.fills),
                "buy_fills": sum(1 for fill in result.fills if fill.side == "buy"),
                "sell_fills": sum(1 for fill in result.fills if fill.side == "sell"),
                "fill_details": tuple(
                    {
                        "side": fill.side,
                        "price": fill.price,
                        "quantity": fill.quantity,
                        "notional": fill.notional,
                    }
                    for fill in result.fills
                ),
                "book_bids": tuple(
                    {"price": price, "quantity": quantity}
                    for price, quantity in result.book_bids
                ),
                "book_asks": tuple(
                    {"price": price, "quantity": quantity}
                    for price, quantity in result.book_asks
                ),
                "cash": result.portfolio.cash,
                "inventory": result.portfolio.inventory,
                "fees_paid": result.portfolio.fees_paid,
                "equity": result.equity,
            }
        )

    return tuple(rows)


def backtest_report_data(
    results: Sequence[BacktestStepResult],
    metadata: dict[str, Any] | None = None,
    initial_equity: float = 0.0,
) -> dict[str, Any]:
    """Return summary and step rows in one report-ready object."""

    return {
        "metadata": metadata or {},
        "summary": backtest_summary_to_dict(results, initial_equity=initial_equity),
        "rows": backtest_results_to_rows(results),
    }


def backtest_report_to_json(
    results: Sequence[BacktestStepResult],
    metadata: dict[str, Any] | None = None,
    initial_equity: float = 0.0,
) -> str:
    """Serialize report-ready backtest data as formatted JSON."""

    return json.dumps(
        backtest_report_data(results, metadata=metadata, initial_equity=initial_equity),
        indent=2,
    )


def save_backtest_report_json(
    results: Sequence[BacktestStepResult],
    path: str | Path,
    metadata: dict[str, Any] | None = None,
    initial_equity: float = 0.0,
) -> None:
    """Write report-ready backtest data to a JSON file."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        backtest_report_to_json(
            results,
            metadata=metadata,
            initial_equity=initial_equity,
        ),
        encoding="utf-8",
    )
