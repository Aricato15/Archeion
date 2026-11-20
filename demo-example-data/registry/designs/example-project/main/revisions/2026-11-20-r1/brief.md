# Brief: Example-Project

## Purpose
A small online bookshop where readers find a book, add it to a cart, pay, and get a receipt. It is a made-up project that shows what a design looks like in Archeion.

## Users
- **Readers** browse and buy from a phone or a laptop.
- **The shop owner** adds books and sees orders.

## Scope
- Catalogue with search by title, author and ISBN.
- A cart that survives a reload.
- Checkout through a hosted payment page.
- An emailed receipt once the order is paid.
- Stock levels, so an out-of-stock book can't be ordered.

## Non-goals
- Storing card data. Payment happens on the provider's page.
- Reviews, recommendations and loyalty points.
- Shipping label printing (the carrier question is open).

## Constraints
- One service with one SQLite database file that only it opens.
- A hosted payment page, so the shop never sees a card number.

## Success
- A reader goes from search to paid order in under two minutes.
- No card data in the database or the logs.
