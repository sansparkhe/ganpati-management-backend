"""Money helpers.

Every rupee value in this project is a `decimal.Decimal` quantised to 2 places.
Floats are never used for arithmetic; the only place a float appears is JSON
serialisation, because JSON has no decimal type.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value: Any) -> Decimal:
    """Coerce anything DB/aggregation-shaped into a 2dp Decimal.

    `SUM()` returns `Decimal` on PostgreSQL but may return a float on SQLite,
    so aggregate results always pass through here.
    """
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def percentage(part: Decimal | int | float, whole: Decimal | int | float) -> float:
    """Percentage rounded to 2 decimals; 0.0 when the denominator is zero."""
    whole_dec = Decimal(str(whole))
    if whole_dec == 0:
        return 0.0
    result = (Decimal(str(part)) / whole_dec) * Decimal("100")
    return float(result.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))
