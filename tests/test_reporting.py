import json

import pytest

from avellaneda_stoikov.backtest import BacktestStepResult
from avellaneda_stoikov.execution import Fill
from avellaneda_stoikov.model import Quote
from avellaneda_stoikov.portfolio import PortfolioState
from avellaneda_stoikov.reporting import (
    backtest_report_data,
    backtest_report_to_json,
    backtest_results_to_rows,
    backtest_summary_to_dict,
    save_backtest_report_json,
)


def sample_results() -> tuple[BacktestStepResult, ...]:
    quote = Quote(bid=99.0, ask=101.0, reservation_price=100.0, spread=2.0)
    return (
        BacktestStepResult(
            mid_price=100.0,
            market_spread=2.0,
            book_bids=((99.0, 1.0),),
            book_asks=((101.0, 1.0),),
            quote=quote,
            fills=(Fill(side="buy", price=99.0, quantity=1.0),),
            portfolio=PortfolioState(cash=-99.1, inventory=1.0, fees_paid=0.1),
            equity=0.9,
        ),
        BacktestStepResult(
            mid_price=100.0,
            market_spread=2.0,
            book_bids=((99.0, 1.0),),
            book_asks=((101.0, 1.0),),
            quote=quote,
            fills=(Fill(side="sell", price=101.0, quantity=1.0),),
            portfolio=PortfolioState(cash=1.8, inventory=0.0, fees_paid=0.2),
            equity=1.8,
        ),
    )


def test_backtest_summary_to_dict_returns_plain_summary_metrics() -> None:
    summary = backtest_summary_to_dict(sample_results())

    assert summary["final_equity"] == pytest.approx(1.8)
    assert summary["final_inventory"] == pytest.approx(0.0)
    assert summary["total_fills"] == 2
    assert summary["buy_fills"] == 1
    assert summary["sell_fills"] == 1
    assert summary["total_fees"] == pytest.approx(0.2)


def test_backtest_results_to_rows_returns_one_row_per_step() -> None:
    rows = backtest_results_to_rows(sample_results())

    assert rows == (
        {
            "step": 1,
            "mid_price": 100.0,
            "market_spread": 2.0,
            "bid": 99.0,
            "ask": 101.0,
            "reservation_price": 100.0,
            "spread": 2.0,
            "bid_distance_from_mid": 1.0,
            "ask_distance_from_mid": 1.0,
            "quote_levels": (
                {
                    "level": 1,
                    "bid": 99.0,
                    "ask": 101.0,
                    "reservation_price": 100.0,
                    "spread": 2.0,
                },
            ),
            "fills": 1,
            "buy_fills": 1,
            "sell_fills": 0,
            "fill_details": (
                {
                    "side": "buy",
                    "price": 99.0,
                    "quantity": 1.0,
                    "notional": 99.0,
                },
            ),
            "book_bids": ({"price": 99.0, "quantity": 1.0},),
            "book_asks": ({"price": 101.0, "quantity": 1.0},),
            "cash": -99.1,
            "inventory": 1.0,
            "fees_paid": 0.1,
            "equity": 0.9,
        },
        {
            "step": 2,
            "mid_price": 100.0,
            "market_spread": 2.0,
            "bid": 99.0,
            "ask": 101.0,
            "reservation_price": 100.0,
            "spread": 2.0,
            "bid_distance_from_mid": 1.0,
            "ask_distance_from_mid": 1.0,
            "quote_levels": (
                {
                    "level": 1,
                    "bid": 99.0,
                    "ask": 101.0,
                    "reservation_price": 100.0,
                    "spread": 2.0,
                },
            ),
            "fills": 1,
            "buy_fills": 0,
            "sell_fills": 1,
            "fill_details": (
                {
                    "side": "sell",
                    "price": 101.0,
                    "quantity": 1.0,
                    "notional": 101.0,
                },
            ),
            "book_bids": ({"price": 99.0, "quantity": 1.0},),
            "book_asks": ({"price": 101.0, "quantity": 1.0},),
            "cash": 1.8,
            "inventory": 0.0,
            "fees_paid": 0.2,
            "equity": 1.8,
        },
    )


def test_backtest_report_data_combines_metadata_summary_and_rows() -> None:
    metadata = {"symbol": "BTCUSDT", "fill_model": "touch"}

    report_data = backtest_report_data(sample_results(), metadata=metadata)

    assert report_data["metadata"] == metadata
    assert report_data["summary"]["final_equity"] == pytest.approx(1.8)
    assert len(report_data["rows"]) == 2


def test_backtest_report_to_json_serializes_report_data() -> None:
    report_json = backtest_report_to_json(sample_results(), metadata={"symbol": "BTCUSDT"})
    parsed_report = json.loads(report_json)

    assert parsed_report["metadata"]["symbol"] == "BTCUSDT"
    assert parsed_report["summary"]["final_equity"] == pytest.approx(1.8)
    assert parsed_report["rows"][0]["step"] == 1


def test_save_backtest_report_json_writes_report_file(tmp_path) -> None:
    path = tmp_path / "reports" / "backtest.json"

    save_backtest_report_json(sample_results(), path, metadata={"symbol": "BTCUSDT"})

    parsed_report = json.loads(path.read_text(encoding="utf-8"))
    assert parsed_report["metadata"]["symbol"] == "BTCUSDT"
    assert parsed_report["summary"]["total_fills"] == 2
