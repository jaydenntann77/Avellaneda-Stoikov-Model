# Avellaneda-Stoikov Market Making Model

This project is a from-scratch implementation of the Avellaneda-Stoikov market making model, built as a research/backtesting project rather than a production trading system.

The goal is to understand how an inventory-aware market maker should quote bid and ask prices, then test that logic on real order book data in a clean and explainable way.

## The Problem

A market maker provides liquidity by continuously quoting:

```text
bid = price where we are willing to buy
ask = price where we are willing to sell
```

The market maker hopes to earn the spread by buying low and selling high. The risk is inventory.

If the bid keeps getting filled, the market maker becomes long. If price falls after that, the position loses money. If the ask keeps getting filled, the market maker becomes short. If price rises after that, the position loses money.

So the core problem is:

```text
How should we place bid and ask quotes while controlling inventory risk?
```

## The Avellaneda-Stoikov Idea

A naive market maker quotes symmetrically around the mid-price:

```text
bid = mid - half_spread
ask = mid + half_spread
```

The Avellaneda-Stoikov model instead quotes around a reservation price.

The reservation price is the market maker's own inventory-adjusted fair price:

```text
reservation = mid - inventory * gamma * sigma^2 * horizon
```

If inventory is long, the reservation price moves below the mid-price. This makes the ask more aggressive and the bid less aggressive, encouraging the strategy to reduce inventory.

If inventory is short, the reservation price moves above the mid-price. This makes the bid more aggressive and the ask less aggressive, encouraging the strategy to buy back inventory.

The model also gives an approximate optimal spread:

```text
spread = gamma * sigma^2 * horizon
       + (2 / gamma) * log(1 + gamma / k)
```

Then the quotes are:

```text
bid = reservation - spread / 2
ask = reservation + spread / 2
```

## What This Repository Will Build

The project will be built step by step:

```text
1. Pure Avellaneda-Stoikov quote formulas
2. Tests that verify the model intuition
3. Parameter estimation for volatility and order-arrival decay
4. Backtesting on replayed market data
5. Real Binance Futures L2 order book reconstruction
6. Fees, latency, inventory limits, and execution approximations
7. A self-contained HTML report for sharing results
```

## Run The Current Backtest

The repository includes a small saved BTCUSDT Binance Futures depth sample:

```text
data/raw/btcusdt_futures_depth_live.jsonl
```

Run the example backtest with:

```bash
python examples/run_real_data_backtest.py
```

This uses the current simple touch-fill approximation, fee accounting, and
summary metrics. It is still a research toy, not a production trading simulator.

To refresh the saved Binance sample with live public BTCUSDT Futures depth data:

```bash
python examples/capture_live_binance_depth.py
```

This overwrites `data/raw/btcusdt_futures_depth_live.jsonl` with 10 top-of-book
depth snapshots captured one second apart.

Preview the current static report locally with:

```bash
cd reports
python -m http.server 8765
```

Then open:

```text
http://127.0.0.1:8765
```
