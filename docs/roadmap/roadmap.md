# Roadmap

_Last updated: 2026-11-15_

## Now
- Use the viewer day to day and fix what gets in the way (PATCH releases).
- Done on 2026-11-15: the viewer app, phases 0–4 ([the plan](2026-11-15-viewer-app-plan.md)), and in 0.2.0 the multi-project registry with read-only project sources, per-project feedback and the private registry folder ([ADR 0006](../decisions/0006-multi-project-registry.md), [ADR 0007](../decisions/0007-keep-project-information-out-of-the-repo.md)).

## Next
- Install the portable project inbox into the shared workspace plugin, so each project's session can pick up its feedback.
- Keep the registry pages' `verified` dates current, and add a group page whenever related projects form a new system.

## Later
- Phase 5: "Ask Claude" from the browser through the Agent SDK ([ADR 0002](../decisions/0002-viewer-app-and-claude-feedback-loop.md), option B). Needs its own go-ahead.
