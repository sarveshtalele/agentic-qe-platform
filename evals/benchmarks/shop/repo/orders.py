"""Places an order: reserve stock, then price it."""
from cart import Cart
from inventory import Inventory
from pricing import order_total


def place_order(cart: Cart, inventory: Inventory, discount_percent=0):
    if not cart.items:
        raise ValueError("cart is empty")
    for sku, line in cart.items.items():
        inventory.reserve(sku, line["quantity"])
    return {"lines": len(cart.items), "total": order_total(cart.total(discount_percent))}
