# Checkout module

`module.shop.checkout` · verified at `probe-fixture-v1`

Coordinates checkout by reserving inventory and creating an order.

- Claims: `module.shop.checkout.claim.summary`
- Evidence: `src/shop/checkout.py:4-11`

## Responsibilities

- Reserves inventory before creating an order.
  - Claims: `module.shop.checkout.claim.orchestration`
  - Evidence: `src/shop/checkout.py:4-11`

## Public interfaces

- `CheckoutService.checkout` — Checks out a SKU and quantity and returns an order identifier.
  - Claims: `module.shop.checkout.claim.interface`
  - Evidence: `src/shop/checkout.py:4-11`

## Dependencies

- `module.shop.inventory` — Uses Inventory.reserve to reserve the requested quantity.
  - Claims: `module.shop.checkout.claim.inventory-dependency`
  - Evidence: `src/shop/checkout.py:4-11`, `src/shop/inventory.py:1-3`

## Relations

- depends_on → module.shop.inventory
  - Claims: `module.shop.checkout.claim.inventory-dependency`
  - Evidence: `src/shop/checkout.py:4-11`, `src/shop/inventory.py:1-3`
