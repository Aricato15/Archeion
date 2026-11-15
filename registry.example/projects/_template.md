---
name: example-service
path: ../example-service
# root: private   # only for a project in a folder granted in ARCHEION_ROOTS; path is then relative to it
group: example-system
status: active
kind: service
ports: [20100]
depends_on: []
verified: 2026-11-15
---

# Example service

_One paragraph: what this project is for. Copy this file to `<name>.md` and fill it in. Files starting with `_` are ignored by the registry._

## Owns
- The data or responsibility only this project has.

## Exposes
- What other projects use from it (an API, a library, files). Link to its own API docs instead of copying them.

## Depends on
- Other projects it calls or imports. List them in `depends_on` above too, so the maps show them.
