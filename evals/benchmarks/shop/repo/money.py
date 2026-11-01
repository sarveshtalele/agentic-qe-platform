"""Money helpers. Amounts are rounded to two decimals, half up."""
from decimal import ROUND_HALF_UP, Decimal


def round_money(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def format_money(value, symbol="Rs "):
    return f"{symbol}{round_money(value):,.2f}"
