"""Helpers for preparing backtest results for reports and demos."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from avellaneda_stoikov.backtest import BacktestStepResult, summarize_backtest


def backtest_summary_to_dict(results: Sequence[BacktestStepResult]) -> dict[str, float | int]:
    """Return summary metrics as a plain dictionary."""

    return asdict(summarize_backtest(results))


def backtest_results_to_rows(results: Sequence[BacktestStepResult]) -> tuple[dict[str, Any], ...]:
    """Return one plain row per backtest step for tables or charts."""

    rows = []
    for index, result in enumerate(results, start=1):
        rows.append(
            {
                "step": index,
                "bid": result.quote.bid,
                "ask": result.quote.ask,
                "reservation_price": result.quote.reservation_price,
                "spread": result.quote.spread,
                "fills": len(result.fills),
                "buy_fills": sum(1 for fill in result.fills if fill.side == "buy"),
                "sell_fills": sum(1 for fill in result.fills if fill.side == "sell"),
                "cash": result.portfolio.cash,
                "inventory": result.portfolio.inventory,
                "fees_paid": result.portfolio.fees_paid,
                "equity": result.equity,
            }
        )

    return tuple(rows)


def backtest_report_data(results: Sequence[BacktestStepResult]) -> dict[str, Any]:
    """Return summary and step rows in one report-ready object."""

    return {
        "summary": backtest_summary_to_dict(results),
        "rows": backtest_results_to_rows(results),
    }


def backtest_report_to_json(results: Sequence[BacktestStepResult]) -> str:
    """Serialize report-ready backtest data as formatted JSON."""

    return json.dumps(backtest_report_data(results), indent=2)


def save_backtest_report_json(
    results: Sequence[BacktestStepResult],
    path: str | Path,
) -> None:
    """Write report-ready backtest data to a JSON file."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(backtest_report_to_json(results), encoding="utf-8")
