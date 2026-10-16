"""Canadian mortgage payment maths.

Fixed-rate Canadian mortgages compound the quoted rate semi-annually, so the
monthly rate is not rate / 12.
"""


def monthly_rate(annual_rate: float) -> float:
    """Effective monthly rate for a nominal annual rate compounded semi-annually."""
    return (1 + annual_rate / 2) ** (2 / 12) - 1


def mortgage_payment(
    price: float,
    annual_rate: float,
    down_payment_pct: float = 0.20,
    amortization_years: int = 25,
) -> float:
    """Monthly payment on a fixed-rate Canadian mortgage.

    `annual_rate` and `down_payment_pct` are fractions (0.05, 0.20). Excludes
    property tax, strata fees, insurance and CMHC premiums.
    """
    if price <= 0:
        raise ValueError("price must be positive")
    if not 0 <= down_payment_pct < 1:
        raise ValueError("down_payment_pct must be in [0, 1)")
    if annual_rate < 0:
        raise ValueError("annual_rate must not be negative")
    if amortization_years <= 0:
        raise ValueError("amortization_years must be positive")

    principal = price * (1 - down_payment_pct)
    n = amortization_years * 12
    i = monthly_rate(annual_rate)
    if i == 0:
        return principal / n
    return principal * i / (1 - (1 + i) ** -n)
