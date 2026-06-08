import pytest

from avellaneda_stoikov.backtest import (
    BacktestStepResult,
    run_backtest,
    run_backtest_on_binance_jsonl,
    run_backtest_on_binance_messages,
    run_backtest_step,
    summarize_backtest,
)
from avellaneda_stoikov.execution import Fill
from avellaneda_stoikov.model import ModelParameters, Quote
from avellaneda_stoikov.order_book import OrderBookSnapshot
from avellaneda_stoikov.portfolio import PortfolioState


def base_params() -> ModelParameters:
    return ModelParameters(gamma=0.1, sigma=1.0, horizon=1.0, k=1.0)


def test_backtest_step_generates_quote_and_marks_unchanged_portfolio() -> None:
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)])
    portfolio = PortfolioState()

    result = run_backtest_step(
        snapshot=snapshot,
        portfolio=portfolio,
        params=base_params(),
        quote_quantity=1.0,
    )

    assert result.fills == ()
    assert result.portfolio == portfolio
    assert result.equity == pytest.approx(0.0)
    assert result.mid_price == pytest.approx(100.0)
    assert result.market_spread == pytest.approx(2.0)
    assert result.book_bids == ((99.0, 1.0),)
    assert result.book_asks == ((101.0, 1.0),)
    assert result.quote.reservation_price == pytest.approx(snapshot.mid_price)


def test_backtest_step_can_use_touch_fill_model() -> None:
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)])
    narrow_params = ModelParameters(gamma=0.1, sigma=0.0, horizon=0.0, k=100.0)

    result = run_backtest_step(
        snapshot=snapshot,
        portfolio=PortfolioState(),
        params=narrow_params,
        quote_quantity=1.0,
        fill_model="touch",
    )

    assert len(result.fills) == 2
    assert result.fills[0].side == "buy"
    assert result.fills[1].side == "sell"
    assert result.portfolio.inventory == pytest.approx(0.0)
    assert result.equity > 0.0


def test_backtest_step_applies_marketable_fill_to_portfolio() -> None:
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)])
    params = ModelParameters(gamma=0.1, sigma=1.0, horizon=1.0, k=100.0)

    result = run_backtest_step(
        snapshot=snapshot,
        portfolio=PortfolioState(inventory=-20.0),
        params=params,
        quote_quantity=2.0,
    )

    assert len(result.fills) == 1
    assert result.fills[0].side == "buy"
    assert result.fills[0].price == pytest.approx(101.0)
    assert result.portfolio.inventory == pytest.approx(-18.0)
    assert result.portfolio.cash == pytest.approx(-202.0)
    assert result.equity == pytest.approx(-2002.0)


def test_backtest_step_skips_buy_that_would_exceed_inventory_limit() -> None:
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)])
    params = ModelParameters(gamma=0.1, sigma=1.0, horizon=1.0, k=100.0)
    portfolio = PortfolioState(inventory=-20.0)

    result = run_backtest_step(
        snapshot=snapshot,
        portfolio=portfolio,
        params=params,
        quote_quantity=2.0,
        max_absolute_inventory=17.0,
    )

    assert result.fills == ()
    assert result.portfolio == portfolio


def test_backtest_step_skips_sell_that_would_exceed_inventory_limit() -> None:
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)])
    params = ModelParameters(gamma=0.1, sigma=1.0, horizon=1.0, k=100.0)
    portfolio = PortfolioState(inventory=20.0)

    result = run_backtest_step(
        snapshot=snapshot,
        portfolio=portfolio,
        params=params,
        quote_quantity=2.0,
        max_absolute_inventory=17.0,
    )

    assert result.fills == ()
    assert result.portfolio == portfolio


def test_backtest_step_uses_current_inventory_when_generating_quote() -> None:
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)])
    flat_result = run_backtest_step(
        snapshot=snapshot,
        portfolio=PortfolioState(),
        params=base_params(),
        quote_quantity=1.0,
    )
    long_result = run_backtest_step(
        snapshot=snapshot,
        portfolio=PortfolioState(inventory=1.0),
        params=base_params(),
        quote_quantity=1.0,
    )

    assert long_result.quote.reservation_price < flat_result.quote.reservation_price


def test_backtest_runs_snapshots_in_sequence() -> None:
    snapshots = [
        OrderBookSnapshot.from_levels(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)]),
        OrderBookSnapshot.from_levels(bids=[(100.0, 1.0)], asks=[(102.0, 1.0)]),
    ]
    params = ModelParameters(gamma=0.1, sigma=1.0, horizon=1.0, k=100.0)

    results = run_backtest(
        snapshots=snapshots,
        initial_portfolio=PortfolioState(inventory=-20.0),
        params=params,
        quote_quantity=2.0,
    )

    assert len(results) == 2
    assert results[0].portfolio.inventory == pytest.approx(-18.0)
    assert results[1].quote.reservation_price == pytest.approx(102.8)


def test_backtest_can_use_next_snapshot_fill_model() -> None:
    snapshots = [
        OrderBookSnapshot.from_levels(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)]),
        OrderBookSnapshot.from_levels(bids=[(101.5, 1.0)], asks=[(102.0, 1.0)]),
    ]
    params = ModelParameters(gamma=0.1, sigma=0.0, horizon=0.0, k=100.0)

    results = run_backtest(
        snapshots=snapshots,
        initial_portfolio=PortfolioState(),
        params=params,
        quote_quantity=1.0,
        fill_model="next_snapshot",
    )

    assert len(results) == 2
    assert len(results[0].fills) == 1
    assert results[0].fills[0].side == "sell"
    assert results[0].fills[0].price == pytest.approx(results[0].quote.ask)
    assert results[0].portfolio.inventory == pytest.approx(-1.0)
    assert results[1].fills == ()
    assert results[1].portfolio.inventory == pytest.approx(-1.0)


def test_backtest_can_use_next_snapshot_quote_ladder() -> None:
    snapshots = [
        OrderBookSnapshot.from_levels(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)]),
        OrderBookSnapshot.from_levels(bids=[(100.35, 1.0)], asks=[(101.0, 1.0)]),
    ]
    params = ModelParameters(gamma=0.1, sigma=0.0, horizon=0.0, k=100.0)

    results = run_backtest(
        snapshots=snapshots,
        initial_portfolio=PortfolioState(),
        params=params,
        quote_quantity=1.0,
        fill_model="next_snapshot",
        quote_levels=3,
        quote_level_spacing=0.1,
    )

    assert len(results[0].quote_levels) == 3
    assert len(results[0].fills) == 3
    assert results[0].fills[0].side == "sell"
    assert results[0].fills[1].side == "sell"
    assert results[0].fills[2].side == "sell"
    assert results[0].portfolio.inventory == pytest.approx(-3.0)


def test_backtest_rejects_empty_snapshot_sequence() -> None:
    with pytest.raises(ValueError, match="at least one snapshot is required"):
        run_backtest(
            snapshots=[],
            initial_portfolio=PortfolioState(),
            params=base_params(),
            quote_quantity=1.0,
        )


def test_backtest_runs_on_binance_messages() -> None:
    messages = [
        {
            "bids": [["99.0", "1.0"]],
            "asks": [["101.0", "1.0"]],
        },
        {
            "b": [["100.0", "1.0"]],
            "a": [["102.0", "1.0"]],
        },
    ]

    results = run_backtest_on_binance_messages(
        messages=messages,
        initial_portfolio=PortfolioState(),
        params=base_params(),
        quote_quantity=1.0,
    )

    assert len(results) == 2
    assert results[0].quote.reservation_price == pytest.approx(100.0)
    assert results[1].quote.reservation_price == pytest.approx(100.5)


def test_backtest_runs_on_binance_jsonl_file(tmp_path) -> None:
    path = tmp_path / "depth.jsonl"
    path.write_text(
        '{"bids": [["99.0", "1.0"]], "asks": [["101.0", "1.0"]]}\n'
        '{"b": [["100.0", "1.0"]], "a": [["102.0", "1.0"]]}\n',
        encoding="utf-8",
    )

    results = run_backtest_on_binance_jsonl(
        path=path,
        initial_portfolio=PortfolioState(),
        params=base_params(),
        quote_quantity=1.0,
    )

    assert len(results) == 2
    assert results[0].quote.reservation_price == pytest.approx(100.0)
    assert results[1].quote.reservation_price == pytest.approx(100.5)


def test_backtest_summary_reports_basic_metrics() -> None:
    quote = Quote(bid=99.0, ask=101.0, reservation_price=100.0, spread=2.0)
    results = (
        BacktestStepResult(
            mid_price=100.0,
            market_spread=2.0,
            book_bids=((99.0, 1.0),),
            book_asks=((101.0, 1.0),),
            quote=quote,
            fills=(Fill(side="buy", price=99.0, quantity=1.0),),
            portfolio=PortfolioState(inventory=1.0, fees_paid=0.1),
            equity=0.0,
        ),
        BacktestStepResult(
            mid_price=100.0,
            market_spread=2.0,
            book_bids=((99.0, 1.0),),
            book_asks=((101.0, 1.0),),
            quote=quote,
            fills=(Fill(side="sell", price=101.0, quantity=1.0),),
            portfolio=PortfolioState(inventory=-3.0, fees_paid=0.2),
            equity=5.0,
        ),
        BacktestStepResult(
            mid_price=101.0,
            market_spread=2.0,
            book_bids=((100.0, 1.0),),
            book_asks=((102.0, 1.0),),
            quote=quote,
            fills=(Fill(side="sell", price=102.0, quantity=2.0),),
            portfolio=PortfolioState(inventory=2.0, fees_paid=0.3),
            equity=2.0,
        ),
    )

    summary = summarize_backtest(results)

    assert summary.final_equity == pytest.approx(2.0)
    assert summary.final_inventory == pytest.approx(2.0)
    assert summary.total_fills == 3
    assert summary.buy_fills == 1
    assert summary.sell_fills == 2
    assert summary.traded_notional == pytest.approx(404.0)
    assert summary.total_fees == pytest.approx(0.3)
    assert summary.max_absolute_inventory == pytest.approx(3.0)
    assert summary.min_equity == pytest.approx(0.0)
    assert summary.max_equity == pytest.approx(5.0)
    assert summary.max_drawdown == pytest.approx(3.0)


def test_backtest_summary_rejects_empty_results() -> None:
    with pytest.raises(ValueError, match="at least one backtest result is required"):
        summarize_backtest([])


def test_backtest_step_rejects_invalid_execution_settings() -> None:
    snapshot = OrderBookSnapshot.from_levels(bids=[(99.0, 1.0)], asks=[(101.0, 1.0)])

    with pytest.raises(ValueError, match="quote_quantity must be positive"):
        run_backtest_step(
            snapshot=snapshot,
            portfolio=PortfolioState(),
            params=base_params(),
            quote_quantity=0.0,
        )

    with pytest.raises(ValueError, match="fee_rate cannot be negative"):
        run_backtest_step(
            snapshot=snapshot,
            portfolio=PortfolioState(),
            params=base_params(),
            quote_quantity=1.0,
            fee_rate=-0.001,
        )

    with pytest.raises(ValueError, match="max_absolute_inventory must be positive"):
        run_backtest_step(
            snapshot=snapshot,
            portfolio=PortfolioState(),
            params=base_params(),
            quote_quantity=1.0,
            max_absolute_inventory=0.0,
        )

    with pytest.raises(ValueError, match='fill_model must be "marketable", "touch", or "next_snapshot"'):
        run_backtest_step(
            snapshot=snapshot,
            portfolio=PortfolioState(),
            params=base_params(),
            quote_quantity=1.0,
            fill_model="unknown",
        )
