"""Run the basic Avellaneda-Stoikov backtest on saved Binance depth data."""

from datetime import datetime, timezone

from avellaneda_stoikov.backtest import run_backtest
from avellaneda_stoikov.binance import (
    load_binance_depth_messages_jsonl,
    reconstruct_snapshots_from_binance_messages,
)
from avellaneda_stoikov.backtest import summarize_backtest
from avellaneda_stoikov.calibration import (
    estimate_arrival_intensity_from_snapshots,
    estimate_price_volatility,
    estimate_rolling_price_volatility,
)
from avellaneda_stoikov.model import ModelParameters
from avellaneda_stoikov.portfolio import PortfolioState
from avellaneda_stoikov.reporting import backtest_summary_to_dict, save_backtest_report_json


DATA_PATH = "data/raw/btcusdt_futures_depth_live.jsonl"
REPORT_PATH = "reports/latest_backtest.json"
INITIAL_EQUITY = 100_000.0
INITIAL_INVENTORY = -0.5
GAMMA_CANDIDATES = (0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005)
K_QUOTE_DISTANCES = (0.1, 0.2, 0.5, 1.0, 2.0, 4.0, 8.0, 12.0)
TIME_STEP_SECONDS = 0.25
QUOTE_QUANTITY = 0.01
QUOTE_LEVELS = 5
QUOTE_LEVEL_SPACING = 0.05
FEE_RATE = 0.00001
MAX_ABSOLUTE_INVENTORY = 1.0
FILL_MODEL = "next_snapshot"
DRAWDOWN_PENALTY = 0.1
INVENTORY_PENALTY = 0.5
ROLLING_VOL_WINDOW = 60


def main() -> None:
    messages = load_binance_depth_messages_jsonl(DATA_PATH)
    snapshots = reconstruct_snapshots_from_binance_messages(messages)
    start_time_ms = _message_time_ms(messages[0])
    end_time_ms = _message_time_ms(messages[-1])
    mid_prices = [snapshot.mid_price for snapshot in snapshots]
    sigma = estimate_price_volatility(
        mid_prices=mid_prices,
        time_step_seconds=TIME_STEP_SECONDS,
    )
    rolling_sigmas = estimate_rolling_price_volatility(
        mid_prices=mid_prices,
        time_step_seconds=TIME_STEP_SECONDS,
        window_size=min(ROLLING_VOL_WINDOW, len(mid_prices)),
    )
    arrival_calibration = estimate_arrival_intensity_from_snapshots(
        snapshots=snapshots,
        quote_distances=K_QUOTE_DISTANCES,
        time_step_seconds=TIME_STEP_SECONDS,
    )
    gamma, calibration_trials = _select_gamma(
        snapshots=snapshots,
        sigma=sigma,
        k=arrival_calibration.fit.k,
    )
    params = ModelParameters(
        gamma=gamma,
        sigma=sigma,
        horizon=len(snapshots) * TIME_STEP_SECONDS,
        k=arrival_calibration.fit.k,
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
            "data_window": {
                "start_time_ms": start_time_ms,
                "end_time_ms": end_time_ms,
                "start_time_utc": _format_utc_timestamp(start_time_ms),
                "end_time_utc": _format_utc_timestamp(end_time_ms),
            },
            "model_parameters": {
                "gamma": params.gamma,
                "sigma": params.sigma,
                "horizon": params.horizon,
                "k": params.k,
            },
            "calibration": {
                "sigma_method": "realized mid-price variance",
                "rolling_sigma_window": min(ROLLING_VOL_WINDOW, len(mid_prices)),
                "rolling_sigma_min": min(rolling_sigmas),
                "rolling_sigma_max": max(rolling_sigmas),
                "k_method": "next-snapshot L2 crossing intensity fit",
                "k_quote_distances": K_QUOTE_DISTANCES,
                "k_fill_intensities": arrival_calibration.fill_intensities,
                "base_intensity": arrival_calibration.fit.base_intensity,
                "gamma_method": "grid search maximizing net_pnl - drawdown_penalty * max_drawdown - inventory_penalty * max_abs_inventory",
                "gamma_candidates": GAMMA_CANDIDATES,
                "gamma_trials": calibration_trials,
                "drawdown_penalty": DRAWDOWN_PENALTY,
                "inventory_penalty": INVENTORY_PENALTY,
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
                "Sigma is estimated from realized BTCUSDT mid-price changes, "
                "k is fitted from L2 next-snapshot crossing intensity by quote "
                "distance, and gamma is selected by a risk-adjusted backtest "
                "objective. The strategy places a multi-level quote ladder "
                "around the Avellaneda-Stoikov reservation price."
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


def _select_gamma(snapshots, sigma: float, k: float) -> tuple[float, tuple[dict[str, float | int], ...]]:
    trials = []
    initial_cash = INITIAL_EQUITY - INITIAL_INVENTORY * snapshots[0].mid_price
    for gamma in GAMMA_CANDIDATES:
        params = ModelParameters(
            gamma=gamma,
            sigma=sigma,
            horizon=len(snapshots) * TIME_STEP_SECONDS,
            k=k,
        )
        results = run_backtest(
            snapshots=snapshots,
            initial_portfolio=PortfolioState(
                cash=initial_cash,
                inventory=INITIAL_INVENTORY,
            ),
            params=params,
            quote_quantity=QUOTE_QUANTITY,
            fee_rate=FEE_RATE,
            max_absolute_inventory=MAX_ABSOLUTE_INVENTORY,
            fill_model=FILL_MODEL,
            quote_levels=QUOTE_LEVELS,
            quote_level_spacing=QUOTE_LEVEL_SPACING,
        )
        summary = summarize_backtest(results)
        net_pnl = summary.final_equity - INITIAL_EQUITY
        objective = (
            net_pnl
            - DRAWDOWN_PENALTY * summary.max_drawdown
            - INVENTORY_PENALTY * summary.max_absolute_inventory
        )
        trials.append(
            {
                "gamma": gamma,
                "objective": objective,
                "net_pnl": net_pnl,
                "max_drawdown": summary.max_drawdown,
                "max_absolute_inventory": summary.max_absolute_inventory,
                "total_fills": summary.total_fills,
            }
        )

    best_trial = max(trials, key=lambda trial: trial["objective"])
    return float(best_trial["gamma"]), tuple(trials)


def _message_time_ms(message: dict) -> int | None:
    timestamp = message.get("E") or message.get("T")
    return int(timestamp) if timestamp is not None else None


def _format_utc_timestamp(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


if __name__ == "__main__":
    main()
