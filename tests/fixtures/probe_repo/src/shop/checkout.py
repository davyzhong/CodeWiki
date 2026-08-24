from shop.inventory import Inventory


class CheckoutService:
    def __init__(self, inventory: Inventory) -> None:
        self.inventory = inventory

    def checkout(self, sku: str, quantity: int) -> str:
        if not self.inventory.reserve(sku, quantity):
            raise ValueError("inventory reservation failed")
        return "order-created"

