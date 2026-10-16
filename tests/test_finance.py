import pytest

from open_data_analyst.finance import monthly_rate, mortgage_payment


def _balance_after_all_payments(price, rate, down, years):
    """Independent check: pay the loan down month by month and see what is left."""
    i = monthly_rate(rate)
    balance = price * (1 - down)
    payment = mortgage_payment(price, rate, down, years)
    for _ in range(years * 12):
        balance = balance * (1 + i) - payment
    return balance


def test_monthly_rate_is_semi_annual_compounding():
    # Six monthly periods compound to the half-year rate of r / 2.
    assert (1 + monthly_rate(0.05)) ** 6 == pytest.approx(1 + 0.05 / 2)


def test_loan_is_fully_paid_off():
    assert _balance_after_all_payments(900_000, 0.0549, 0.20, 25) == pytest.approx(0, abs=1e-6)


def test_more_down_payment_lowers_payment():
    assert mortgage_payment(800_000, 0.05, 0.30) < mortgage_payment(800_000, 0.05, 0.20)


def test_zero_rate_is_straight_division():
    assert mortgage_payment(600_000, 0.0, 0.20, 20) == pytest.approx(480_000 / 240)


def test_defaults_are_20_percent_down_25_years():
    assert mortgage_payment(750_000, 0.05) == mortgage_payment(750_000, 0.05, 0.20, 25)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"price": 0, "annual_rate": 0.05},
        {"price": 500_000, "annual_rate": -0.01},
        {"price": 500_000, "annual_rate": 0.05, "down_payment_pct": 1.0},
        {"price": 500_000, "annual_rate": 0.05, "amortization_years": 0},
    ],
)
def test_invalid_inputs_are_rejected(kwargs):
    with pytest.raises(ValueError):
        mortgage_payment(**kwargs)
