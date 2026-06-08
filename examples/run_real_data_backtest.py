"""Run the basic Avellaneda-Stoikov backtest on saved Binance depth data."""

from avellaneda_stoikov.backtest import run_backtest_on_binance_jsonl
from avellaneda_stoikov.model import ModelParameters
from avellaneda_stoikov.portfolio import PortfolioState
from avellaneda_stoikov.reporting import backtest_summary_to_dict, save_backtest_report_json


def main() -> None:
    results = run_backtest_on_binance_jsonl(
        path="data/raw/btcusdt_futures_depth_live.jsonl",
        initial_portfolio=PortfolioState(),
        params=ModelParameters(gamma=0.1, sigma=0.0, horizon=0.0, k=100.0),
        quote_quantity=0.001,
        fee_rate=0.0004,
        max_absolute_inventory=0.01,
        fill_model="touch",
    )
    summary = backtest_summary_to_dict(results)
    report_path = "reports/latest_backtest.json"
    save_backtest_report_json(results, report_path)

    print("Avellaneda-Stoikov real-data backtest")
    print(f"steps: {len(results)}")
    print(f"final equity: {summary['final_equity']:.8f}")
    print(f"final inventory: {summary['final_inventory']:.8f}")
    print(f"total fills: {summary['total_fills']}")
    print(f"buy fills: {summary['buy_fills']}")
    print(f"sell fills: {summary['sell_fills']}")
    print(f"traded notional: {summary['traded_notional']:.8f}")
    print(f"total fees: {summary['total_fees']:.8f}")
    print(f"max drawdown: {summary['max_drawdown']:.8f}")
    print(f"report JSON: {report_path}")


if __name__ == "__main__":
    main()
