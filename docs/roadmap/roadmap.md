# Roadmap

_Last updated: 2026-11-15_

## Now
- Viewer app, phases 0–4: scaffolding, login and root scripts, docs viewer, history and overviews, and the `/inbox` feedback loop. See [the plan](2026-11-15-viewer-app-plan.md).
- Multi-project registry, read-only project sources and per-project feedback ([ADR 0006](../decisions/0006-multi-project-registry.md)), on branch `multi-regis-test` for review.

## Next
- Use the viewer day to day and fix what gets in the way (PATCH releases).
- Install the portable project inbox into the shared workspace plugin, so each project's session can pick up its feedback.
- Keep the registry pages' `verified` dates current, and add a group page whenever related projects form a new system.

## Later
- Phase 5: "Ask Claude" from the browser through the Agent SDK ([ADR 0002](../decisions/0002-viewer-app-and-claude-feedback-loop.md), option B). Needs its own go-ahead.
