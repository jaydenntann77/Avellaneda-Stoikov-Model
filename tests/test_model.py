import pytest

from avellaneda_stoikov.model import ModelParameters, generate_quote, optimal_spread, reservation_price


def base_params() -> ModelParameters:
    return ModelParameters(gamma=0.1, sigma=2.0, horizon=1.0, k=1.5)


def test_flat_inventory_reservation_equals_mid_price() -> None:
    params = base_params()

    reservation = reservation_price(mid_price=100.0, inventory=0.0, params=params)

    assert reservation == pytest.approx(100.0)


def test_long_inventory_pushes_reservation_below_mid_price() -> None:
    params = base_params()

    reservation = reservation_price(mid_price=100.0, inventory=1.0, params=params)

    assert reservation < 100.0


def test_short_inventory_pushes_reservation_above_mid_price() -> None:
    params = base_params()

    reservation = reservation_price(mid_price=100.0, inventory=-1.0, params=params)

    assert reservation > 100.0


def test_generated_quote_is_centered_on_reservation_price() -> None:
    params = base_params()

    quote = generate_quote(mid_price=100.0, inventory=1.0, params=params)

    assert quote.reservation_price == pytest.approx((quote.bid + quote.ask) / 2.0)
    assert quote.spread == pytest.approx(quote.ask - quote.bid)


def test_higher_volatility_widens_spread() -> None:
    low_vol = ModelParameters(gamma=0.1, sigma=1.0, horizon=1.0, k=1.5)
    high_vol = ModelParameters(gamma=0.1, sigma=2.0, horizon=1.0, k=1.5)

    assert optimal_spread(high_vol) > optimal_spread(low_vol)


def test_long_inventory_makes_ask_more_aggressive_than_bid() -> None:
    params = base_params()

    quote = generate_quote(mid_price=100.0, inventory=1.0, params=params)

    distance_from_mid_to_bid = 100.0 - quote.bid
    distance_from_mid_to_ask = quote.ask - 100.0
    assert distance_from_mid_to_ask < distance_from_mid_to_bid


def test_invalid_parameters_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match="gamma must be positive"):
        optimal_spread(ModelParameters(gamma=0.0, sigma=2.0, horizon=1.0, k=1.5))

    with pytest.raises(ValueError, match="k must be positive"):
        optimal_spread(ModelParameters(gamma=0.1, sigma=2.0, horizon=1.0, k=0.0))

    with pytest.raises(ValueError, match="mid_price must be positive"):
        reservation_price(mid_price=0.0, inventory=0.0, params=base_params())
