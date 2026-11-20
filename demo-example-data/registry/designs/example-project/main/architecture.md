# Architecture: Example-Project

One FastAPI service serves the web front end and the API, and owns a single SQLite file for the catalogue, carts and orders. Payment happens on the provider's hosted page. The provider calls the shop back when a payment succeeds, and the shop then sends the receipt.

## Parts
- **Web front end**: the pages readers use.
- **Shop service**: the API, split into catalogue, cart, checkout and receipts.
- **orders.db**: books, carts, orders and stock.
- **Payment provider** and **Email provider**: outside systems.

## Key paths
- *Search*: the front end asks the catalogue, which reads the books table.
- *Checkout*: the cart becomes an order, the reader is sent to the payment page, and the provider's callback marks the order paid and triggers the receipt.

## Order states
An order is `new`, then `paid`, then `shipped`. An unpaid order can be `cancelled`.
