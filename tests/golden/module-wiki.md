# Checkout module

## Scope

| Field | Value |
| --- | --- |
| Knowledge ID | `module.shop.checkout` |
| Repository | `fixture/probe-shop` |
| Branch | `main` |
| Commit | `probe-fixture-v1` |
| Validity | `verified` |

## Summary

Coordinates checkout by reserving inventory and creating an order.

- Claims: `module.shop.checkout.claim.summary`
- Evidence: `src/shop/checkout.py:4-11`

## Responsibilities

### Reserves inventory before creating an order.

- Claims: `module.shop.checkout.claim.orchestration`
- Evidence: `src/shop/checkout.py:4-11`

## Public interfaces

### `CheckoutService.checkout`

Checks out a SKU and quantity and returns an order identifier.

- Claims: `module.shop.checkout.claim.interface`
- Evidence: `src/shop/checkout.py:4-11`

## Dependencies

### `module.shop.inventory`

Uses Inventory.reserve to reserve the requested quantity.

- Claims: `module.shop.checkout.claim.inventory-dependency`
- Evidence: `src/shop/checkout.py:4-11`, `src/shop/inventory.py:1-3`

## Relations

### depends\_on → module.shop.inventory

- Claims: `module.shop.checkout.claim.inventory-dependency`
- Evidence: `src/shop/checkout.py:4-11`, `src/shop/inventory.py:1-3`

## Verified claims

### `module.shop.checkout.claim.interface`

CheckoutService exposes checkout\(sku, quantity\) returning a string.

- Evidence: `src/shop/checkout.py:4-11`

### `module.shop.checkout.claim.inventory-dependency`

CheckoutService depends on Inventory.reserve, which accepts a SKU and quantity and returns a boolean.

- Evidence: `src/shop/checkout.py:4-11`, `src/shop/inventory.py:1-3`

### `module.shop.checkout.claim.orchestration`

CheckoutService.checkout calls Inventory.reserve before returning an order identifier.

- Evidence: `src/shop/checkout.py:4-11`

### `module.shop.checkout.claim.summary`

CheckoutService coordinates checkout by reserving inventory before returning an order identifier.

- Evidence: `src/shop/checkout.py:4-11`
