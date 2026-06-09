# Avellaneda-Stoikov Market Making Model

This project is my attempt to understand market making from first principles,
starting with the Avellaneda-Stoikov model and then forcing it to interact with
real Binance BTCUSDT Futures L2 order book data.

I built it because I wanted to understand what actually happens when a clean theoretical market making model is
put next to noisy order book data, fees, fills, inventory, and calibration.

Live backtest:

https://jaydenntann77.github.io/Avellaneda-Stoikov-Model/

## The Problem

A simple market maker posts a bid and an ask around the mid-price, hoping to buy
low, sell high, and earn the spread.

This is easy until inventory starts building up.

If my bids keep getting hit, I become long. If price drops after that, the
strategy loses money. If my asks keep getting hit, I become short. If price
rises, same problem in the other direction.

So the question is:

```text
How should my quotes change when my inventory changes?
```

That is the part of market making I wanted to make visible.

## Why Avellaneda-Stoikov

The Avellaneda-Stoikov model gives a clean way to think about this problem.
Instead of always quoting symmetrically around the market mid-price, the market
maker quotes around a reservation price.

```text
reservation = mid - inventory * gamma * sigma^2 * horizon
```

This reservation price is basically the market maker's own inventory-adjusted
fair value.

If I am long, the reservation price moves lower. That makes my ask relatively
more attractive and my bid less attractive, nudging the strategy to sell
inventory.

If I am short, the reservation price moves higher. That makes my bid more
attractive and my ask less attractive, and the strategy buys more inventory
back.

## The Core Model

The approximate A-S spread I used is:

```text
spread = gamma * sigma^2 * horizon + (2 / gamma) * log(1 + gamma / k)
```

Then:

```text
bid = reservation - spread / 2
ask = reservation + spread / 2
```

The parameters matter a lot:

- `sigma` controls how risky price movement is.
- `gamma` controls how aggressively the strategy dislikes inventory.
- `k` controls how quickly fills decay as quotes move away from the mid.
- `horizon` controls the remaining risk window.

Theoretically the equations are clean and the parameters seem easy to optimise.
But i realised that the harder part is deciding what these parameters should be when the market is
moving, liquidity is uneven, and the sample is not stationary.

## What I Built

The project currently does four main things.

1. It fetches and stores Binance USD-M Futures L2 depth snapshots for
   BTCUSDT.
2. It reconstructs those snapshots into a normalized order book format.
3. it runs an inventory-aware A-S quote ladder through the data. The ladder
   is still centered on the A-S reservation price, but it places multiple passive
   levels on each side so the replay has enough quote opportunities to inspect.
4. It produces a static HTML backtest that replays the strategy frame by
   frame. The backtest shows:
    - order book depth
    - bid and ask quote paths
    - reservation price
    - fill markers
    - cash, inventory, equity, and PnL
    - calibrated parameters
    - final backtest summary

The backtest lets someone watch how inventory changes the quotes in real time.

## Calibration

I did not want the final version to just use random constants.

For the current backtest:

- `sigma` is estimated from realized BTCUSDT mid-price changes.
- `k` is fitted from empirical next-snapshot crossing intensity at different
  quote distances.
- `gamma` is selected by a grid search over a simple risk-adjusted objective.

The gamma objective is:

```text
net_pnl
- drawdown_penalty * max_drawdown
- inventory_penalty * max_absolute_inventory
```

This is not the same as saying gamma is directly observable from the order book. Gamma is more like a risk preference. In this project, I treat it as a parameter selected empirically for the sample and objective.

The backtest also shows a rolling sigma range. That was useful because it reminded
me that volatility is not really stationary, even inside a short captured
window. The theoretical model is elegant in itself, but the market will keep changing.

## What The Current backtest Shows

The current published backtest uses 240 real Binance L2 frames.

At a high level, it shows:

- a calibrated A-S quote ladder
- a live order book replay
- current equity and PnL updating during replay
- fills accumulating over time
- reservation price moving away from mid when inventory is non-zero
- final PnL, drawdown, inventory, and fill statistics

The most important part to look at is the gap between the mid-price and the
reservation price. That gap is the model reacting to inventory.

## The Data Window

The live backtest currently replays a short Binance BTCUSDT futures L2 snapshot window rather than a multi-day production backtest. I kept this intentionally small so the static site can be lightweight and interactive.

The result should be read as a microstructure replay: it shows how the AS quoting logic reacts to real order book movement, how inventory changes the reservation price, and how fills affect PnL.

It is not yet evidence that the strategy is profitable over time. To test that properly, the next step would be running the same engine over longer historical windows across different volatility regimes and market sessions. And also different fee tiers.

## Limitations

Things the research does not model yet:

- queue position
- latency
- partial fills
- order cancellations
- adverse selection beyond observed book movement
- longer intraday sessions
- rolling recalibration during the replay
- real exchange order management
