# Project registry

One page per project or sub-project. The YAML frontmatter holds the structural facts, and the maps and the project tree are generated from it. The body holds cross-project notes only ([ADR 0006](../../docs/decisions/0006-multi-project-registry.md)).

```yaml
---
name: example-collector                       # id; defaults to the file name
title: Example collector                      # display name (else the first heading)
root: projects                                # a root granted on the Settings page (ARCHEION_ROOTS)
path: example-service/collectors/example      # relative to that root (without root: relative to this repo, inside ARCHEION_WORKSPACE_ROOT)
parent: example-service                       # makes it a sub-project
group: example-system                         # a page in ../groups/; sub-projects inherit their parent's
status: active                                # active | planned | paused | archived
kind: collector                               # free text: service, frontend, library...
ports: [20100]
depends_on: [example-service]                 # projects it calls or imports: the arrows on the maps
docs_dir: docs                                # where its own docs live inside path
verified: 2026-11-15                          # when the frontmatter was last checked
---
```

- **New projects:** the viewer's Settings page lists every root's projects and registers the ones you pick. Or `scripts/archeion.ps1 projects scan` lists the folders in your roots that have no page yet, and `--write` creates stub pages here (it never overwrites one). `--only <name>` picks some, `--root <name>` scans one root.
- **Projects outside the workspace:** grant their folder on the viewer's Settings page or in `ARCHEION_ROOTS` (`configure.bat`) and set `root:` on the page. `path` is then relative to that folder ([ADR 0008](../../docs/decisions/0008-named-project-roots.md)). `projects list` shows the tree and any problems, which the viewer's Projects page also shows.
- **Keep facts in their home:** a project's own facts (endpoints, commands, internal design) stay in its own repo. The viewer shows its README, CLAUDE.md and docs folder live, read-only.
- **Starting point:** copy `_template.md` to `<name>.md` for a page written by hand.
