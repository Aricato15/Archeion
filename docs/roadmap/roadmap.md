# Roadmap

_Last updated: 2026-11-15_

## Now
- Use the viewer day to day and fix what gets in the way (PATCH releases).
- Done on 2026-11-15: the viewer app, phases 0–4 ([the plan](2026-11-15-viewer-app-plan.md)), and in 0.2.0 the multi-project registry with read-only project sources, per-project feedback and the private registry folder ([ADR 0006](../decisions/0006-multi-project-registry.md), [ADR 0007](../decisions/0007-keep-project-information-out-of-the-repo.md)).

## Next
- Decide on [ADR 0008](../decisions/0008-named-project-roots.md) (named roots, so projects outside the workspace can be registered without moving) and [ADR 0009](../decisions/0009-archeion-plugin-for-project-sessions.md) (an Archeion plugin, installed at user level and versioned separately, that gives every project session its inbox and system context). If accepted, build 0008 first, then 0009, each as a MINOR release ([the plan](2026-11-15-named-roots-and-plugin-plan.md), which starts from a clean slate). 0009 replaces the plan to install the portable project inbox into the shared workspace plugin.
- Keep the registry pages' `verified` dates current, and add a group page whenever related projects form a new system.

## Later
- Phase 5: "Ask Claude" from the browser through the Agent SDK ([ADR 0002](../decisions/0002-viewer-app-and-claude-feedback-loop.md), option B). Needs its own go-ahead.
