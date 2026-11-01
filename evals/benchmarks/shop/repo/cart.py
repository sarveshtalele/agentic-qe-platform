"""Shopping cart: holds items and works out what the customer owes."""
from money import round_money
from validators import require_positive


class Cart:
    def __init__(self):
        self.items = {}

    def add(self, sku, price, quantity=1):
        require_positive(quantity, "quantity")
        require_positive(price, "price")
        if sku in self.items:
            self.items[sku]["quantity"] += quantity
        else:
            self.items[sku] = {"price": price, "quantity": quantity}

    def remove(self, sku):
        del self.items[sku]

    def subtotal(self):
        return round_money(sum(i["price"] * i["quantity"] for i in self.items.values()))

    def total(self, discount_percent=0):
        if discount_percent < 0 or discount_percent > 100:
            raise ValueError("discount must be between 0 and 100")
        discount = self.subtotal() * discount_percent / 10
        return round_money(self.subtotal() - discount)
