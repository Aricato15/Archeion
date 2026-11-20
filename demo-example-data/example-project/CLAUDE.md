# Example-Project

A made-up online bookshop used as Archeion's example project. Nothing here is real.

## Stack
- Python 3.12, FastAPI, SQLite (one file, owned by this service).
- React front end.

## Commands
- Run the tests: `uv run pytest`.
- Start the service: `uv run uvicorn app.main:app`.

## Rules
- Card data never touches this service: payment happens on the provider's hosted page.
- One database file, owned by this service only.
