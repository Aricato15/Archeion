# Roadmap

_Last updated: 2026-11-15_

## Now
- Use the viewer day to day and fix what gets in the way (PATCH releases).
- Done on 2026-11-15, unreleased: the Settings page, to manage roots and register projects from the viewer ([ADR 0010](../decisions/0010-manage-roots-and-registration-in-the-viewer.md)). Stub pages no longer set `verified`.
- Done on 2026-11-15: in 0.3.0 named roots, so projects outside the workspace can be registered without moving ([ADR 0008](../decisions/0008-named-project-roots.md)), and in 0.4.0 the Archeion plugin for project sessions, installed at user level with its own version, 0.1.0 ([ADR 0009](../decisions/0009-archeion-plugin-for-project-sessions.md), [the plan](2026-11-15-named-roots-and-plugin-plan.md)).
- Done on 2026-11-15: the viewer app, phases 0–4 ([the plan](2026-11-15-viewer-app-plan.md)), and in 0.2.0 the multi-project registry with read-only project sources, per-project feedback and the private registry folder ([ADR 0006](../decisions/0006-multi-project-registry.md), [ADR 0007](../decisions/0007-keep-project-information-out-of-the-repo.md)).

## Next
- Merge `feat/named-roots-and-plugin` into `main` after the viewer checks in the [end-to-end notes](../notes/2026-11-15-named-roots-and-plugin-e2e.md).
- Keep the registry pages' `verified` dates current, and add a group page whenever related projects form a new system.

## Later
- Phase 5: "Ask Claude" from the browser through the Agent SDK ([ADR 0002](../decisions/0002-viewer-app-and-claude-feedback-loop.md), option B). Needs its own go-ahead.
