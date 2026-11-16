# Roadmap

_Last updated: 2026-11-16_

## Now
- Code studies ([ADR 0019](../decisions/0019-code-studies.md), [the plan](2026-11-16-code-studies-plan.md)), on the branch `feat/code-studies`: `/study <project>` saves dated snapshots of a project's code that the project page's **Study** tab draws as component maps and sequence, ER, activity and state diagrams.
- Use the viewer day to day and fix what gets in the way (PATCH releases).
- Done on 2026-11-15, unreleased: diagrams for system design, with Mermaid's ELK layout and icon packs for architecture diagrams ([ADR 0014](../decisions/0014-diagrams-for-system-design.md), [how to write them](../guides/diagrams.md)).
- Done on 2026-11-15, in 0.5.0: the Settings page, to manage roots and register projects from the viewer ([ADR 0010](../decisions/0010-manage-roots-and-registration-in-the-viewer.md)); creating the admin password in the viewer on a fresh start ([ADR 0011](../decisions/0011-create-the-admin-password-in-the-viewer.md)); no root granted by default ([ADR 0012](../decisions/0012-no-root-granted-by-default.md)); and the Claude CLI panel, which shows the [terminal workflow](../guides/claude-cli.md). `feat/named-roots-and-plugin` is merged into `main`.
- Done on 2026-11-15: in 0.3.0 named roots, so projects outside the workspace can be registered without moving ([ADR 0008](../decisions/0008-named-project-roots.md)), and in 0.4.0 the Archeion plugin for project sessions, installed at user level with its own version, 0.1.0 ([ADR 0009](../decisions/0009-archeion-plugin-for-project-sessions.md), [the plan](2026-11-15-named-roots-and-plugin-plan.md)).
- Done on 2026-11-15: the viewer app, phases 0–4 ([the plan](2026-11-15-viewer-app-plan.md)), and in 0.2.0 the multi-project registry with read-only project sources, per-project feedback and the private registry folder ([ADR 0006](../decisions/0006-multi-project-registry.md), [ADR 0007](../decisions/0007-keep-project-information-out-of-the-repo.md)).

## Next
- Interactive project maps: draw the registry maps with React Flow and elkjs, with click-through, hover highlighting and folding groups ([ADR 0015](../decisions/0015-interactive-registry-maps.md), proposed on 2026-11-15). Accept the ADR first, after the checks it lists.
- Run the viewer checks in the [end-to-end notes](../notes/2026-11-15-named-roots-and-plugin-e2e.md) on `main`. The branch was merged on 2026-11-15 before they were run, so fix anything they find in PATCH releases.
- A `brainstorm` skill for new, empty projects. The terminal stays the main way to work with Claude; the viewer shows the results.
- Keep the registry pages' `verified` dates current, and add a group page whenever related projects form a new system.

## Later
- Phase 5: "Ask Claude" from the browser through the Agent SDK ([ADR 0002](../decisions/0002-viewer-app-and-claude-feedback-loop.md), option B). Needs its own go-ahead. Deferred on 2026-11-15: Claude runs in the terminal, and the viewer is for viewing and feedback.
