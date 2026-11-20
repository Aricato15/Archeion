# 0001: Use a hosted payment page

- Status: Accepted (2026-11-12)

## Context
The shop is small and must not carry the burden of storing card data.

## Decision
Checkout sends the reader to the payment provider's hosted page. The shop only learns whether the payment succeeded.

## Consequences
- No card data in the shop's database or logs.
- The checkout flow depends on the provider's confirmation call back.
