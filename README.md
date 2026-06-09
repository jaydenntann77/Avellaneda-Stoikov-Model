# Avellaneda-Stoikov Market Making Model

This project is my attempt to understand market making from first principles,
starting with the Avellaneda-Stoikov model and then forcing it to interact with
real Binance BTCUSDT Futures L2 order book data.

I did not build this as a production trading bot. I built it because I wanted to
understand what actually happens when a clean theoretical market making model is
put next to noisy order book data, fees, fills, inventory, and calibration.

Live report:

https://jaydenntann77.github.io/Avellaneda-Stoikov-Model/

## The Question I Was Trying To Answer

A simple market maker posts a bid and an ask around the mid-price, hoping to buy
low, sell high, and earn the spread.

That sounds easy until inventory starts building up.

If my bids keep getting hit, I become long. If price drops after that, the
strategy loses money. If my asks keep getting hit, I become short. If price
rises, same problem in the other direction.

So the more interesting question is not just:

```text
Where should I quote around the mid-price?
```

It is:

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
attractive and my ask less attractive, nudging the strategy to buy inventory
back.

That single shift is the main idea I wanted the dashboard to show. If the
reservation price is not visibly moving, then the project is just another random
spread quoting toy.

## The Core Model

The approximate A-S spread I used is:

```text
spread = gamma * sigma^2 * horizon
       + (2 / gamma) * log(1 + gamma / k)
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

One thing I learned pretty quickly is that the equations are the clean part.
The harder part is deciding what these parameters should be when the market is
moving, liquidity is uneven, and the sample is not stationary.

## What I Built

The project currently does four main things.

First, it fetches and stores Binance USD-M Futures L2 depth snapshots for
BTCUSDT.

Second, it reconstructs those snapshots into a normalized order book format.

Third, it runs an inventory-aware A-S quote ladder through the data. The ladder
is still centered on the A-S reservation price, but it places multiple passive
levels on each side so the replay has enough quote opportunities to inspect.

Fourth, it produces a static HTML report that replays the strategy frame by
frame. The report shows:

- order book depth
- bid and ask quote paths
- reservation price
- fill markers
- cash, inventory, equity, and PnL
- calibrated parameters
- final backtest summary

The point of the report is not just to show a final PnL number. The point is to
let someone watch how inventory changes the quotes.

## Calibration

I did not want the final version to just use random constants.

For the current report:

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

This is not the same as saying gamma is directly observable from the order book.
It is not. Gamma is more like a risk preference. In this project, I treat it as
a parameter selected empirically for the sample and objective.

The report also shows a rolling sigma range. That was useful because it reminded
me that volatility is not really stationary, even inside a short captured
window. The theoretical model is elegant, but the market keeps changing its
personality.

## What The Current Report Shows

The current published report uses 240 real Binance L2 frames.

At a high level, it shows:

- a calibrated A-S quote ladder
- a live order book replay
- current equity and PnL updating during replay
- fills accumulating over time
- reservation price moving away from mid when inventory is non-zero
- final PnL, drawdown, inventory, and fill statistics

The most important part to look at is the gap between the mid-price and the
reservation price. That gap is the model reacting to inventory.

## What I Learned

The main thing I learned is that market making is less about "predicting price"
and more about surviving inventory.

A few specific lessons:

1. **Inventory is not a side detail.**
   It directly changes the quote center. This is the core A-S insight.

2. **Fill modeling matters a lot.**
   If I assume every quote fills whenever it touches the book, the backtest
   looks active but unrealistic. If I make fills too strict, nothing happens.
   The current next-snapshot crossing approximation is still simple, but it is
   at least tied to actual order book movement.

3. **Calibration is fragile.**
   A parameter set that looks reasonable on one sample can be too wide, too
   passive, or too aggressive on another. This is exactly why I added empirical
   sigma and k calibration.

4. **A nice PnL number can be misleading.**
   Without looking at inventory, drawdown, fees, and fills, a final equity number
   does not say much.

5. **The theory is clean. The implementation is messy.**
   The formula fits on a few lines. The hard parts are data quality, execution
   assumptions, queue position, fees, latency, and deciding what is honest to
   show.

## Limitations

This is still a research backtest.

Things it does not model yet:

- queue position
- latency
- partial fills
- order cancellations
- adverse selection beyond observed book movement
- longer intraday sessions
- rolling recalibration during the replay
- real exchange order management

So I would not describe this as a trading system. I would describe it as a
market microstructure research project and a visual explanation of the
Avellaneda-Stoikov inventory mechanism.

## What I Would Improve Next

The next improvements I would make are:

- compare A-S against a naive symmetric quote ladder
- run longer intraday samples
- recalibrate sigma and k on a rolling basis
- add queue-position assumptions
- model latency and cancellations
- separate maker rebates / taker fees by venue
- add a volatility-regime view

The comparison against a naive strategy is probably the most important next
step. It would make the value of the reservation price adjustment much more
obvious.

## How I Would Explain This In An Interview

The short version:

> I implemented the Avellaneda-Stoikov market making model and replayed it on
> real Binance BTCUSDT L2 order book data. The main thing I wanted to study was
> how inventory changes the market maker's reservation price, and therefore its
> bid/ask quotes. I also calibrated volatility and fill-intensity from the data,
> then selected risk aversion through a grid search objective. The project taught
> me that the theoretical model is elegant, but the practical difficulty is
> execution modeling, calibration stability, and inventory risk.

That is the actual thing I learned from building this.
