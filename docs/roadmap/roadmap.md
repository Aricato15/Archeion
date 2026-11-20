# Roadmap

_Last updated: 2026-11-20_

Now, Next and Later are the open work. What shipped is under **Released**, one section per version, newest first.

## Now
- **1.5.0, in progress: the design Checklist** ([ADR 0029](../decisions/0029-design-checklist.md), [the plan](2026-11-20-design-checklist-plan.md)). A design gets a checklist of the features, ideas and decisions the user and Claude agreed on. Claude proposes and maintains it, you review and comment, and nothing applies until you confirm. A roadmap is generated from it. The viewer's Roadmap page is split by version, with the current one first (this page's new layout).

## Next
- Use designs on a real project, end to end: a first real design from the Design tab, then a first `/archeion:consume-design` in the project's session. Fix what that finds in PATCH releases.
- Run the viewer checks in the [end-to-end notes](../notes/2026-11-15-named-roots-and-plugin-e2e.md) on `main`. The branch was merged on 2026-11-15 before they were run, so fix anything they find in PATCH releases.
- Use groups, promotion and break-down on a real system, and a real `/report-guided` conversation, and fix what that finds.
- Next for the maps ([the proposal](2026-11-17-diagram-scaling-proposal.md)): re-run `/study --refresh` on a large project to check the sub-groups, then build the clustering pass in `study scan` that suggests them, a remembered view per map, and the dependency matrix if still needed. Delete `temp_feedback/` (local screenshots, untracked) when the diagram issues are settled.
- Run a first real `/study` from the viewer and check a map with every registered project (ADR 0015's last check).
- Keep the registry pages' `verified` dates current, and add a group page whenever related projects form a new system.
- Use the viewer day to day and fix what gets in the way (PATCH releases).

## Later
- Phase 5: "Ask Claude" from the browser through the Agent SDK ([ADR 0002](../decisions/0002-viewer-app-and-claude-feedback-loop.md), option B). Needs its own go-ahead. Deferred on 2026-11-15: Claude runs in the terminal, and the viewer is for viewing and feedback.

## Released

### 1.4.0 (2026-11-19)
- **Groups with a home, and promoting a project to a group** ([ADR 0027](../decisions/0027-groups-with-a-home-and-promotion.md), [the plan](2026-11-19-groups-and-promotion-plan.md), [the brainstorm](../notes/2026-11-19-groups-as-promoted-projects-brainstorm.md)). A group has a folder and everything a project has, a project can be promoted into one, a group's study reads its members' studies, **Break down** registers a group's folders as members, and a study no longer needs git.
- **Create a new project or group from the viewer** ([ADR 0028](../decisions/0028-create-a-project-from-the-viewer.md)).

### 1.3.0 (2026-11-18)
- **PDF reports of a project** ([ADR 0025](../decisions/0025-project-pdf-reports.md), [the plan](2026-11-17-project-report-plan.md)). The project page's **Report** button makes a standard report (you pick and order the sections) or a guided one (Claude plans it from your prompt and outline, and labels what it wrote), with every diagram in the PDF.

### 1.2.0 (2026-11-17)
- A **Glossary** tab on each project page ([ADR 0023](../decisions/0023-project-glossaries.md)), interactive flows, logic and states with a Mermaid switch and side panels ([ADR 0024](../decisions/0024-interactive-study-views.md)), clearer maps, and sub-group guidance in `/study` and `/design`.
- **Designing and planning a registered project from Archeion** ([ADR 0022](../decisions/0022-design-and-plan-a-project.md), [the plan](2026-11-17-design-and-plan-plan.md)). A **Design** tab and `/design <project>` work a project's brief, architecture, plan and decisions out with the rest of the system in view; you approve a revision; **Hand off** delivers it as a package that the project's session turns into its own docs with `/archeion:consume-design` (plugin 0.3.0).

### 1.0.0 (2026-11-16)
- **Code studies** ([ADR 0019](../decisions/0019-code-studies.md), [the plan](2026-11-16-code-studies-plan.md)). `/study <project>` saves dated snapshots of a project's code that the project page's **Study** tab draws as component maps and sequence, ER, activity and state diagrams. Studies started from the viewer are conversations, answered by on-demand Claude ([ADR 0020](../decisions/0020-study-conversations-and-on-demand-claude.md)).
- The maps are interactive (React Flow and ELK, [ADR 0015](../decisions/0015-interactive-registry-maps.md)), and every diagram zooms and pans. Claude jobs can be watched in a window or run headless, up to 2 at a time ([ADR 0021](../decisions/0021-claude-jobs-windows-headless-and-limits.md)).

### Before 1.0.0
- 2026-11-15, unreleased then: diagrams for system design, with Mermaid's ELK layout and icon packs ([ADR 0014](../decisions/0014-diagrams-for-system-design.md), [how to write them](../guides/diagrams.md)).
- 0.5.0 (2026-11-15): the Settings page, to manage roots and register projects from the viewer ([ADR 0010](../decisions/0010-manage-roots-and-registration-in-the-viewer.md)); creating the admin password in the viewer on a fresh start ([ADR 0011](../decisions/0011-create-the-admin-password-in-the-viewer.md)); no root granted by default ([ADR 0012](../decisions/0012-no-root-granted-by-default.md)); and the Claude CLI panel, which shows the [terminal workflow](../guides/claude-cli.md).
- 0.4.0 and 0.3.0 (2026-11-15): the Archeion plugin for project sessions, installed at user level with its own version ([ADR 0009](../decisions/0009-archeion-plugin-for-project-sessions.md), [the plan](2026-11-15-named-roots-and-plugin-plan.md)), and named roots, so projects outside the workspace can be registered without moving ([ADR 0008](../decisions/0008-named-project-roots.md)).
- 0.2.0 and the viewer app (2026-11-15): the viewer, phases 0–4 ([the plan](2026-11-15-viewer-app-plan.md)), the multi-project registry with read-only project sources, per-project feedback and the private registry folder ([ADR 0006](../decisions/0006-multi-project-registry.md), [ADR 0007](../decisions/0007-keep-project-information-out-of-the-repo.md)).
