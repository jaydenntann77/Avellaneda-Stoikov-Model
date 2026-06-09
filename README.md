# Avellaneda-Stoikov Market Making Model

An inventory-aware market making research project built around the
Avellaneda-Stoikov model, real Binance USD-M Futures L2 order book data, and a
static replay dashboard designed to make the strategy behavior inspectable.

The project answers one core question:

```text
How should a market maker quote bid and ask prices while managing inventory risk?
```

## Live Report

The static dashboard is intended to be published with GitHub Pages:

```text
https://jaydenntann77.github.io/Avellaneda-Stoikov-Model/
```

The repository includes a GitHub Actions workflow that deploys the `docs/`
folder to Pages on pushes to `main`.

If GitHub Pages is not enabled yet, serve it locally:

```bash
cd reports
python -m http.server 8765
```

Then open:

```text
http://127.0.0.1:8765
```

## What It Shows

The report replays real BTCUSDT Futures depth snapshots through a calibrated
Avellaneda-Stoikov quote ladder.

It includes:

- current equity, PnL, and fills during replay
- bid/ask quote paths
- reservation price movement
- live order book ladder
- fill markers over time
- final backtest metrics
- calibrated model parameters

The important visual idea is the reservation price:

```text
reservation = mid - inventory * gamma * sigma^2 * horizon
```

When inventory changes, the reservation price shifts away from the mid-price.
That shifts the bid/ask quotes and encourages the strategy to reduce inventory
risk.

## Model

The approximate Avellaneda-Stoikov spread is:

```text
spread = gamma * sigma^2 * horizon
       + (2 / gamma) * log(1 + gamma / k)
```

Quotes are placed around the reservation price:

```text
bid = reservation - spread / 2
ask = reservation + spread / 2
```

This implementation extends the single quote into a multi-level quote ladder so
the replay has enough passive quote opportunities to be visually useful while
still staying anchored to the A-S reservation price.

## Calibration

Rather than relying only on hard-coded parameters, the backtest runner calibrates
the main model inputs from the saved L2 sample:

- `sigma`: estimated from realized BTCUSDT mid-price variance
- `k`: fitted from next-snapshot L2 crossing intensity by quote distance
- `gamma`: selected by grid search over a risk-adjusted objective

The gamma objective is:

```text
net_pnl
- drawdown_penalty * max_drawdown
- inventory_penalty * max_absolute_inventory
```

The report also records a rolling sigma range to show that volatility is not
stationary even inside the captured replay window.

## Data Pipeline

The saved dataset is a newline-delimited JSON file of Binance USD-M Futures
depth snapshots:

```text
data/raw/btcusdt_futures_depth_live.jsonl
```

To refresh it with live public Binance data:

```bash
python examples/capture_live_binance_depth.py
```

The current capture script records 240 snapshots at 0.25 second intervals.

## Run The Backtest

```bash
python examples/run_real_data_backtest.py
```

This writes:

```text
reports/latest_backtest.json
```

The report page reads that JSON directly:

```text
reports/index.html
```

## Development

Install the package in editable mode:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
python -m pytest
```

## Repository Structure

```text
src/avellaneda_stoikov/
  model.py          # A-S reservation price and spread formulas
  calibration.py    # sigma, k, rolling volatility, empirical intensity helpers
  order_book.py     # normalized L2 order book snapshot objects
  binance.py        # Binance depth loading/capture/reconstruction
  execution.py      # fill models and quote-ladder fill logic
  portfolio.py      # cash, inventory, fees, mark-to-market accounting
  backtest.py       # strategy replay loop and summary metrics
  reporting.py      # JSON serialization for the static report

examples/
  capture_live_binance_depth.py
  run_real_data_backtest.py

reports/
  index.html
  latest_backtest.json

docs/
  GitHub Pages copy of the static report
```

## Limitations

This is a research backtest, not a production trading system.

Important simplifications:

- fill logic is a next-snapshot approximation
- no queue position model
- no exchange latency simulation
- no adverse selection model beyond realized book movement
- no live order management or risk system
- calibration is sample-specific and should be re-run on new sessions

The point of the project is not to claim production profitability. The point is
to make the mechanics of inventory-aware market making visible, testable, and
grounded in real L2 data.
