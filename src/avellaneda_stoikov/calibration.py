"""Parameter calibration helpers for the Avellaneda-Stoikov model."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import exp, log, sqrt

from avellaneda_stoikov.order_book import OrderBookSnapshot


@dataclass(frozen=True)
class ArrivalIntensityFit:
    """Fitted parameters for lambda(delta) = A * exp(-k * delta)."""

    base_intensity: float
    k: float


@dataclass(frozen=True)
class EmpiricalArrivalIntensity:
    """Observed fill intensities by quote distance plus exponential fit."""

    quote_distances: tuple[float, ...]
    fill_intensities: tuple[float, ...]
    fit: ArrivalIntensityFit


def estimate_price_volatility(mid_prices: Sequence[float], time_step_seconds: float) -> float:
    """Estimate price volatility from evenly spaced mid-price observations.

    The original A-S paper models the mid-price as an additive Brownian motion:

        dS = sigma dW

    That means sigma should be in price units per sqrt(second), not log-return
    units. For example, BTCUSDT sigma here means roughly "USDT per sqrt(second)".
    """

    _validate_mid_prices(mid_prices)
    if time_step_seconds <= 0:
        raise ValueError("time_step_seconds must be positive.")

    # Price changes are the realized shocks in the Brownian mid-price model.
    # If prices are sampled every dt seconds, Var(delta_price) ~= sigma^2 * dt.
    price_changes = [
        current_price - previous_price
        for previous_price, current_price in zip(mid_prices, mid_prices[1:])
    ]

    # We estimate sigma from realized variance. This intentionally uses price
    # differences, not percentage/log returns, to match the paper's formula.
    realized_variance = sum(change**2 for change in price_changes) / len(price_changes)
    return sqrt(realized_variance / time_step_seconds)


def estimate_rolling_price_volatility(
    mid_prices: Sequence[float],
    time_step_seconds: float,
    window_size: int,
) -> tuple[float, ...]:
    """Estimate volatility over rolling windows of mid-price observations."""

    _validate_mid_prices(mid_prices)
    if time_step_seconds <= 0:
        raise ValueError("time_step_seconds must be positive.")
    if window_size < 2:
        raise ValueError("window_size must be at least 2.")
    if window_size > len(mid_prices):
        raise ValueError("window_size cannot exceed the number of mid-prices.")

    return tuple(
        estimate_price_volatility(
            mid_prices[index : index + window_size],
            time_step_seconds=time_step_seconds,
        )
        for index in range(len(mid_prices) - window_size + 1)
    )


def estimate_arrival_intensity_from_snapshots(
    snapshots: Sequence[OrderBookSnapshot],
    quote_distances: Sequence[float],
    time_step_seconds: float,
) -> EmpiricalArrivalIntensity:
    """Estimate lambda(delta) from next-snapshot order book crossings.

    For each distance, this places a hypothetical bid and ask around the current
    mid-price. A bid opportunity is counted as filled when the next best ask
    moves down to that bid. An ask opportunity is counted as filled when the
    next best bid moves up to that ask.
    """

    if len(snapshots) < 2:
        raise ValueError("at least two snapshots are required.")
    if time_step_seconds <= 0:
        raise ValueError("time_step_seconds must be positive.")
    if len(quote_distances) < 2:
        raise ValueError("at least two quote distances are required.")
    if any(distance < 0 for distance in quote_distances):
        raise ValueError("quote_distances cannot be negative.")

    intensities = []
    for distance in quote_distances:
        fills = 0
        opportunities = 0
        for snapshot, next_snapshot in zip(snapshots, snapshots[1:]):
            bid = snapshot.mid_price - distance
            ask = snapshot.mid_price + distance
            if next_snapshot.best_ask <= bid:
                fills += 1
            if next_snapshot.best_bid >= ask:
                fills += 1
            opportunities += 2

        intensities.append(fills / (opportunities * time_step_seconds))

    positive_pairs = [
        (distance, intensity)
        for distance, intensity in zip(quote_distances, intensities)
        if intensity > 0
    ]
    if len(positive_pairs) < 2:
        raise ValueError("at least two positive fill intensities are required.")

    fit = fit_arrival_intensity_decay(
        quote_distances=[distance for distance, _ in positive_pairs],
        fill_intensities=[intensity for _, intensity in positive_pairs],
    )
    return EmpiricalArrivalIntensity(
        quote_distances=tuple(quote_distances),
        fill_intensities=tuple(intensities),
        fit=fit,
    )


def fit_arrival_intensity_decay(
    quote_distances: Sequence[float],
    fill_intensities: Sequence[float],
) -> ArrivalIntensityFit:
    """Fit the exponential arrival model lambda(delta) = A * exp(-k * delta).

    Args:
        quote_distances: Distances from the mid-price.
        fill_intensities: Observed fill rates at each distance.

    Returns:
        base_intensity: The fitted intensity at zero distance.
        k: The fitted decay parameter used by the A-S spread formula.
    """

    _validate_intensity_inputs(quote_distances, fill_intensities)

    # Taking logs makes the exponential model linear:
    # log(lambda) = log(A) - k * delta.
    # We then fit a simple straight line with least squares.
    x_values = list(quote_distances)
    y_values = [log(intensity) for intensity in fill_intensities]

    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)
    variance_x = sum((x - mean_x) ** 2 for x in x_values)
    if variance_x == 0:
        raise ValueError("quote_distances must contain at least two distinct values.")

    covariance_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
    slope = covariance_xy / variance_x
    intercept = mean_y - slope * mean_x

    # The slope should be negative when intensity decays with distance.
    # Since the model is log(lambda)=log(A)-k*delta, k is -slope.
    k = -slope
    if k <= 0:
        raise ValueError("fitted k must be positive; intensities should decrease with distance.")

    return ArrivalIntensityFit(base_intensity=exp(intercept), k=k)


def _validate_mid_prices(mid_prices: Sequence[float]) -> None:
    if len(mid_prices) < 2:
        raise ValueError("at least two mid-prices are required.")
    if any(price <= 0 for price in mid_prices):
        raise ValueError("mid-prices must be positive.")


def _validate_intensity_inputs(
    quote_distances: Sequence[float],
    fill_intensities: Sequence[float],
) -> None:
    if len(quote_distances) != len(fill_intensities):
        raise ValueError("quote_distances and fill_intensities must have the same length.")
    if len(quote_distances) < 2:
        raise ValueError("at least two distance/intensity points are required.")
    if any(distance < 0 for distance in quote_distances):
        raise ValueError("quote_distances cannot be negative.")
    if any(intensity <= 0 for intensity in fill_intensities):
        raise ValueError("fill_intensities must be positive.")
