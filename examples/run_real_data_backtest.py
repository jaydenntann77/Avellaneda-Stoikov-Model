"""Run the basic Avellaneda-Stoikov backtest on saved Binance depth data."""

from avellaneda_stoikov.backtest import run_backtest
from avellaneda_stoikov.binance import (
    load_binance_depth_messages_jsonl,
    reconstruct_snapshots_from_binance_messages,
)
from avellaneda_stoikov.calibration import estimate_price_volatility
from avellaneda_stoikov.model import ModelParameters
from avellaneda_stoikov.portfolio import PortfolioState
from avellaneda_stoikov.reporting import backtest_summary_to_dict, save_backtest_report_json


DATA_PATH = "data/raw/btcusdt_futures_depth_live.jsonl"
REPORT_PATH = "reports/latest_backtest.json"
INITIAL_EQUITY = 100_000.0
INITIAL_INVENTORY = -0.5
GAMMA = 0.0005
K = 0.3
TIME_STEP_SECONDS = 0.25
QUOTE_QUANTITY = 0.01
QUOTE_LEVELS = 5
QUOTE_LEVEL_SPACING = 0.05
FEE_RATE = 0.00001
MAX_ABSOLUTE_INVENTORY = 1.0
FILL_MODEL = "next_snapshot"


def main() -> None:
    messages = load_binance_depth_messages_jsonl(DATA_PATH)
    snapshots = reconstruct_snapshots_from_binance_messages(messages)
    mid_prices = [snapshot.mid_price for snapshot in snapshots]
    sigma = estimate_price_volatility(
        mid_prices=mid_prices,
        time_step_seconds=TIME_STEP_SECONDS,
    )
    params = ModelParameters(
        gamma=GAMMA,
        sigma=sigma,
        horizon=len(snapshots) * TIME_STEP_SECONDS,
        k=K,
    )
    initial_cash = INITIAL_EQUITY - INITIAL_INVENTORY * snapshots[0].mid_price

    results = run_backtest(
        snapshots=snapshots,
        initial_portfolio=PortfolioState(cash=initial_cash, inventory=INITIAL_INVENTORY),
        params=params,
        quote_quantity=QUOTE_QUANTITY,
        fee_rate=FEE_RATE,
        max_absolute_inventory=MAX_ABSOLUTE_INVENTORY,
        fill_model=FILL_MODEL,
        quote_levels=QUOTE_LEVELS,
        quote_level_spacing=QUOTE_LEVEL_SPACING,
    )
    summary = backtest_summary_to_dict(results, initial_equity=INITIAL_EQUITY)
    save_backtest_report_json(
        results,
        REPORT_PATH,
        initial_equity=INITIAL_EQUITY,
        metadata={
            "title": "Avellaneda-Stoikov BTCUSDT Futures Backtest",
            "symbol": "BTCUSDT",
            "venue": "Binance USD-M Futures",
            "data_path": DATA_PATH,
            "steps": len(results),
            "model_parameters": {
                "gamma": params.gamma,
                "sigma": params.sigma,
                "horizon": params.horizon,
                "k": params.k,
            },
            "execution": {
                "initial_equity": INITIAL_EQUITY,
                "initial_cash": initial_cash,
                "initial_inventory": INITIAL_INVENTORY,
                "fill_model": FILL_MODEL,
                "quote_quantity": QUOTE_QUANTITY,
                "quote_levels": QUOTE_LEVELS,
                "quote_level_spacing": QUOTE_LEVEL_SPACING,
                "fee_rate": FEE_RATE,
                "max_absolute_inventory": MAX_ABSOLUTE_INVENTORY,
            },
            "interpretation": (
                "Sigma is estimated from realized BTCUSDT mid-price changes. "
                "The strategy places a multi-level quote ladder around the "
                "Avellaneda-Stoikov reservation price. The next-snapshot fill "
                "model only fills quotes when the next real order book moves "
                "through them."
            ),
        },
    )

    print("Avellaneda-Stoikov real-data backtest")
    print(f"steps: {len(results)}")
    print(f"initial equity: {summary['initial_equity']:.8f}")
    print(f"initial inventory: {INITIAL_INVENTORY:.8f}")
    print(f"final equity: {summary['final_equity']:.8f}")
    print(f"net pnl: {summary['net_pnl']:.8f}")
    print(f"final inventory: {summary['final_inventory']:.8f}")
    print(f"total fills: {summary['total_fills']}")
    print(f"buy fills: {summary['buy_fills']}")
    print(f"sell fills: {summary['sell_fills']}")
    print(f"traded notional: {summary['traded_notional']:.8f}")
    print(f"total fees: {summary['total_fees']:.8f}")
    print(f"max drawdown: {summary['max_drawdown']:.8f}")
    print(f"report JSON: {REPORT_PATH}")


if __name__ == "__main__":
    main()
