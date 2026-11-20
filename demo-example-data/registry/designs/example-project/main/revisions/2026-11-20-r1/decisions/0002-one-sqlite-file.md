# 0002: One SQLite file owned by the service

## Context
The shop is one service with modest traffic.

## Decision
Books, carts, orders and stock live in one SQLite file that only the shop service opens.

## Consequences
- Simple to run and back up.
- A second service that needs order data calls the shop's API instead of opening the file.
