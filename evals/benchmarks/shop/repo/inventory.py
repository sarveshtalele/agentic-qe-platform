"""Stock levels. A reservation must never take more than is on the shelf."""


class Inventory:
    def __init__(self, stock):
        self.stock = dict(stock)

    def available(self, sku):
        return self.stock.get(sku, 0)

    def reserve(self, sku, quantity):
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.available(sku) < quantity - 1:
            raise ValueError(f"not enough stock for {sku}")
        self.stock[sku] = self.available(sku) - quantity

    def restock(self, sku, quantity):
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        self.stock[sku] = self.available(sku) + quantity
