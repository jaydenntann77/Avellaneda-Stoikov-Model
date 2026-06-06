import pytest

from math import exp

from avellaneda_stoikov.calibration import estimate_price_volatility, fit_arrival_intensity_decay


def test_zero_price_changes_have_zero_volatility() -> None:
    sigma = estimate_price_volatility([100.0, 100.0, 100.0], time_step_seconds=1.0)

    assert sigma == pytest.approx(0.0)


def test_volatility_is_estimated_from_price_changes() -> None:
    sigma = estimate_price_volatility([100.0, 101.0, 100.0], time_step_seconds=1.0)

    assert sigma == pytest.approx(1.0)


def test_longer_time_step_reduces_per_sqrt_second_volatility() -> None:
    one_second_sigma = estimate_price_volatility([100.0, 102.0, 100.0], time_step_seconds=1.0)
    four_second_sigma = estimate_price_volatility([100.0, 102.0, 100.0], time_step_seconds=4.0)

    assert four_second_sigma == pytest.approx(one_second_sigma / 2.0)


def test_invalid_volatility_inputs_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match="at least two mid-prices"):
        estimate_price_volatility([100.0], time_step_seconds=1.0)

    with pytest.raises(ValueError, match="mid-prices must be positive"):
        estimate_price_volatility([100.0, 0.0], time_step_seconds=1.0)

    with pytest.raises(ValueError, match="time_step_seconds must be positive"):
        estimate_price_volatility([100.0, 101.0], time_step_seconds=0.0)


def test_arrival_decay_fit_recovers_known_exponential_parameters() -> None:
    quote_distances = [0.0, 1.0, 2.0, 3.0]
    fill_intensities = [10.0 * exp(-1.5 * distance) for distance in quote_distances]

    fit = fit_arrival_intensity_decay(quote_distances, fill_intensities)

    assert fit.base_intensity == pytest.approx(10.0)
    assert fit.k == pytest.approx(1.5)


def test_arrival_decay_fit_rejects_non_decaying_intensities() -> None:
    with pytest.raises(ValueError, match="fitted k must be positive"):
        fit_arrival_intensity_decay(
            quote_distances=[0.0, 1.0, 2.0],
            fill_intensities=[1.0, 2.0, 3.0],
        )


def test_invalid_arrival_decay_inputs_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match="same length"):
        fit_arrival_intensity_decay([0.0, 1.0], [10.0])

    with pytest.raises(ValueError, match="at least two"):
        fit_arrival_intensity_decay([0.0], [10.0])

    with pytest.raises(ValueError, match="cannot be negative"):
        fit_arrival_intensity_decay([-1.0, 0.0], [10.0, 5.0])

    with pytest.raises(ValueError, match="must be positive"):
        fit_arrival_intensity_decay([0.0, 1.0], [10.0, 0.0])
