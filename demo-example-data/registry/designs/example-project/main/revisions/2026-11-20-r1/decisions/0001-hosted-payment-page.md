# 0001: Use a hosted payment page

## Context
The shop is small, and storing card data would bring rules and risk it doesn't need.

## Decision
Checkout sends the reader to the payment provider's hosted page. The shop only learns whether the payment succeeded.

## Consequences
- No card data in the database or the logs.
- Checkout depends on the provider calling the shop back, so the callback must be retried safely.
