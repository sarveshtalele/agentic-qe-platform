"""Tax and shipping for an order. Tax is 18 percent of the amount, kept to the paisa. Shipping is free from 500 and above."""
from money import round_money

TAX_RATE_PERCENT = 18
FREE_SHIPPING_FROM = 500
SHIPPING_FEE = 40


def tax_for(amount):
    return round_money(amount * TAX_RATE_PERCENT // 100)


def shipping_for(amount):
    if amount > FREE_SHIPPING_FROM:
        return 0
    return SHIPPING_FEE


def order_total(amount):
    return round_money(amount + tax_for(amount) + shipping_for(amount))
