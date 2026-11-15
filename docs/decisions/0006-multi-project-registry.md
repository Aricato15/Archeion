# 0006: Multi-project registry, read-only project sources and per-project feedback

- Status: Proposed (on branch `multi-regis-test`, for review)
- Date: 2026-11-15
- Amends: hard rules 4 and 5 in `CLAUDE.md`, and [ADR 0002](0002-viewer-app-and-claude-feedback-loop.md)

## Context
The workspace holds many projects. Some form a system (example-web calls example-gateway, which calls example-data), some stand alone, and some have sub-projects (example-data's collectors). Version 0.1.0 of the viewer only knew Archeion's own `docs/`:
- Projects were a flat list of pages, with no parents and no groups, and a single hand-drawn map.
- Each project's facts (ports, APIs, stack) would have been copied into Archeion and gone stale, against "one fact in one place".
- Feedback could only reach Archeion's own Claude session, which isn't allowed to edit the project the feedback is about.
- There was one roadmap for everything.

## Decision
1. **Registry with hierarchy.** Each project or sub-project has a page in `docs/system/projects/`, and each group (a system of related projects) a page in `docs/system/groups/`.
   - YAML frontmatter holds the structural facts: `path`, `parent`, `group`, `status`, `kind`, `ports`, `depends_on`, `docs_dir`, `verified`. The page body holds only cross-project notes.
   - Sub-projects inherit their parent's group. Projects without a group are standalone.
   - The backend validates the registry and reports problems (unknown references, parent cycles, paths that are missing, absolute or outside the workspace) instead of failing.
   - The maps are generated from the frontmatter: one overall, one per group, and one per project around it. `docs/interactions/map.md` stops being a hand-drawn diagram.
2. **Read-only project sources.** Every registered project whose `path` resolves inside the workspace (`ARCHEION_WORKSPACE_ROOT`, default `..`) becomes a doc source.
   - The backend serves the project's `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `ROADMAP.md` and its `docs_dir`, and nothing else. It applies the same path rules as for Archeion's docs (no `..`, no dotfiles, allowed types, size limit, no symlinks out).
   - It never writes to a project. History and diffs come from the project's own git repo.
   - Links between docs resolve across sources, so an Archeion page can link to `../example-gateway/docs/api.md` instead of copying it.
   - The watcher follows project roots without recursion and docs folders with recursion, and restarts when the registry changes.
3. **Feedback targets a project.** Feedback items get a `source` (migration 3; `archeion` for existing items). Follow-ups inherit their parent's source.
   - The inbox CLI takes `--project <id>`, or `--here`, which finds the project from the caller's folder. The `/inbox` skill in this repo handles Archeion's own items.
   - A portable skill in `integrations/workspace-core/skills/project-inbox/` does the same for any other project. Installing it into the shared `workspace-core` plugin is a separate step outside this repo.
4. **Roadmaps per project.** The roadmap page shows Archeion's cross-project roadmap first, then each project's own (`docs/roadmap/roadmap.md`, `docs/roadmap.md` or `ROADMAP.md`), filterable by group or project.
5. **Discovery.** `projects scan` lists workspace folders with a `CLAUDE.md`, plus sub-projects (a manifest two levels down, like `collectors/example-collector/pyproject.toml`), that no page points at. `--write` creates stub pages and never overwrites an existing one.

## Consequences
- Hard rule 5 now reads: the backend serves Archeion's docs and, read-only, the listed files of registered projects. Hard rule 4 is unchanged (the frontend still goes only through the backend).
- Only relative paths (`../example-gateway`) are committed. Project contents are read at runtime and never copied into this repo, so publishing Archeion doesn't publish the projects. The private `../PROJECTS.md` is not read at all.
- The API stays backwards compatible: every docs route defaults to `source=archeion`. The `/api/roadmap` response shape changed (`{cross, projects}`), which is fine while the version is `0.y.z` (ADR 0005). This ships as 0.2.0.
- Registry pages need upkeep. The `verified` date and the viewer's warnings show when a page has drifted from its project.
