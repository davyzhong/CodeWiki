from shop.checkout import CheckoutService
from shop.inventory import Inventory


def checkout_order(sku: str, quantity: int) -> str:
    return CheckoutService(Inventory()).checkout(sku, quantity)

