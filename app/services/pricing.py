"""Premium calculator — pure functions, no database.

LAB 1: Premium Calculation

    premium = sum_insured x base_rate x age_factor x tenure_factor x add_on_factor

    The final premium:
    - must never be less than MIN_PREMIUM
    - must be rounded to 2 decimal places

Age factor
    < 25     -> 1.2 (Motor) / 0.8 (Health, Term Life)
    25 - 45  -> 1.0
    46 - 60  -> 1.3
    > 60     -> 1.6
    negative -> PricingError

Tenure factor
    1 yr -> 1.0
    2 yr -> 0.95
    3 yr -> 0.90
    anything else -> PricingError

Add-ons
    Health  CRITICAL_ILLNESS   +15%
    Motor   ZERO_DEPRECIATION  +10%

    Each add-on adds to the factor:
        1.0 + 0.15 = 1.15

    An add-on not available for the product -> PricingError

Sum insured
    - must be greater than 0
    - must be within the product's min/max when provided
    - otherwise -> PricingError

Every function is deliberately simple so it can be unit-tested.
"""

from datetime import date

from app.models import ProductCode


MIN_PREMIUM = 1000.0


TENURE_FACTORS = {
    1: 1.0,
    2: 0.95,
    3: 0.90,
}


ADD_ONS: dict[ProductCode, dict[str, float]] = {
    ProductCode.HEALTH: {
        "CRITICAL_ILLNESS": 0.15,
    },
    ProductCode.MOTOR: {
        "ZERO_DEPRECIATION": 0.10,
    },
    ProductCode.TERM_LIFE: {},
}


class PricingError(ValueError):
    """Raised when a quote request breaks a business rule."""


def age_on(dob: date, on: date | None = None) -> int:
    """Return completed years between dob and on.

    If on is not provided, today's date is used.
    """
    on = on or date.today()

    years = on.year - dob.year

    if (on.month, on.day) < (dob.month, dob.day):
        years -= 1

    return years


def parse_add_ons(raw: str | None) -> list[str]:
    """Convert comma-separated add-ons into uppercase values.

    Example:
        'critical_illness, x'
        -> ['CRITICAL_ILLNESS', 'X']
    """
    return [
        c.strip().upper()
        for c in (raw or "").split(",")
        if c.strip()
    ]


def age_factor(age: int, product: ProductCode) -> float:
    """Return the multiplier for the customer's age band.

    Rules:
        age < 25:
            Motor -> 1.2
            Health/Term Life -> 0.8

        25 - 45 -> 1.0
        46 - 60 -> 1.3
        age > 60 -> 1.6

        negative age -> PricingError
    """

    if age < 0:
        raise PricingError("Age cannot be negative")

    if age < 25:
        if product == ProductCode.MOTOR:
            return 1.2

        return 0.8

    if age <= 45:
        return 1.0

    if age <= 60:
        return 1.3

    return 1.6


def tenure_factor(tenure_years: int) -> float:
    """Return the tenure multiplier.

    Supported values:
        1 -> 1.0
        2 -> 0.95
        3 -> 0.90

    Any other value raises PricingError.
    """

    try:
        return TENURE_FACTORS[tenure_years]
    except KeyError:
        raise PricingError(
            f"Tenure must be 1, 2 or 3 years (got {tenure_years})"
        ) from None


def add_on_factor(
    product: ProductCode,
    add_ons: list[str],
) -> float:
    """Return 1.0 plus the sum of valid add-on loadings.

    Blank entries are ignored.

    Add-on names are normalized by:
        - stripping spaces
        - converting to uppercase

    Example:
        Health + CRITICAL_ILLNESS
        1.0 + 0.15 = 1.15
    """

    factor = 1.0

    available_add_ons = ADD_ONS[product]

    for add_on in add_ons:
        code = add_on.strip().upper()

        # Ignore blank entries
        if not code:
            continue

        # Add-on is not available for this product
        if code not in available_add_ons:
            raise PricingError(
                f"Add-on {code} is not available for {product.value}"
            )

        # Add the loading instead of multiplying it
        factor += available_add_ons[code]

    return factor


def calculate_premium(
    *,
    sum_insured: float,
    base_rate: float,
    age: int,
    tenure_years: int,
    product: ProductCode,
    add_ons: list[str] | None = None,
    min_sum_insured: float | None = None,
    max_sum_insured: float | None = None,
) -> float:
    """Return the annual premium.

    The premium is calculated as:

        sum_insured
        * base_rate
        * age_factor
        * tenure_factor
        * add_on_factor

    The minimum premium is applied before rounding.
    """

    # ---------------------------------------------------------
    # 1. Validate positive sum insured
    # ---------------------------------------------------------
    if sum_insured <= 0:
        raise PricingError("Sum insured must be positive")

    # ---------------------------------------------------------
    # 2. Validate minimum sum insured
    # ---------------------------------------------------------
    if (
        min_sum_insured is not None
        and sum_insured < min_sum_insured
    ):
        raise PricingError(
            f"Sum insured must be at least {min_sum_insured:,.0f}"
        )

    # ---------------------------------------------------------
    # 3. Validate maximum sum insured
    # ---------------------------------------------------------
    if (
        max_sum_insured is not None
        and sum_insured > max_sum_insured
    ):
        raise PricingError(
            f"Sum insured cannot exceed {max_sum_insured:,.0f}"
        )

    # ---------------------------------------------------------
    # 4. Calculate all factors
    # ---------------------------------------------------------
    age_multiplier = age_factor(age, product)

    tenure_multiplier = tenure_factor(tenure_years)

    add_on_multiplier = add_on_factor(
        product,
        add_ons or [],
    )

    # ---------------------------------------------------------
    # 5. Calculate premium
    # ---------------------------------------------------------
    premium = (
        sum_insured
        * base_rate
        * age_multiplier
        * tenure_multiplier
        * add_on_multiplier
    )

    # ---------------------------------------------------------
    # 6. Apply minimum premium
    # ---------------------------------------------------------
    premium = max(premium, MIN_PREMIUM)

    # ---------------------------------------------------------
    # 7. Round to 2 decimal places
    # ---------------------------------------------------------
    return round(premium, 2)