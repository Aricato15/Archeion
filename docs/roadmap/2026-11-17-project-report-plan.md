# Plan: project PDF reports

_Written 2026-11-17. Implements [ADR 0025](../decisions/0025-project-pdf-reports.md), planned for 1.3.0. Branch: `feat/project-pdf-report`. Status: planned, nothing built._

```mermaid
flowchart LR
  P1["Phase 1<br/>Catalog, presets,<br/>CLI"] --> P2["Phase 2<br/>Print route,<br/>diagrams"]
  P2 --> P3["Phase 3<br/>PDF build,<br/>API"]
  P3 --> P4["Phase 4<br/>Dialog, Report tab"]
  P4 --> P5["Phase 5<br/>/report skill,<br/>summary, prompt"]
  P5 --> P6["Phase 6<br/>Docs, verify,<br/>1.3.0"]
```

## Section catalog

| Group | Sections | Source |
|---|---|---|
| Overview | facts (type, ports, group, status, `depends_on`), cross-project notes | registry page |
| Docs | README, CLAUDE.md, CHANGELOG, ROADMAP, each file of the docs folder | read-only project source |
| Study | compact component map, **one diagram per sub-system**, flows, activities, schema, states, interfaces, findings, notes | latest study snapshot |
| Design | brief, architecture, plan, decisions | approved design revision |
| Glossary | terms | glossary JSON |
| System | group map, dependencies and drift | registry |
| Summary | executive summary (Claude), instructions (the user's prompt) | the preset |

## Phases
1. **Catalog, presets, CLI.** `services/reports.py` builds the catalog and validates a preset (known section ids, order, no duplicates). Presets live in `registry/reports/<project>/presets.json`. CLI: `report preflight|catalog|preset list|show|save|delete|build|list|verify`.
2. **Print route.** `/print/report/:project` in the frontend lays out the selected sections in order: cover, table of contents, one section per page break, running header. Diagrams render as static SVG: the compact map, a diagram per sub-system, flows, activities, states and the schema.
3. **PDF build and API.** `report build` opens the print route in headless Edge with a one-time token and writes the PDF. `routers/reports.py`: `/api/reports` (catalog, presets, build, list, download). Every route needs a session, apart from the print route's token.
4. **Dialog and tab.** A **Report** button on the project page opens the configuration (grouped checkboxes, `@dnd-kit` ordering, sub-system diagram toggles, page size and orientation, cover, contents, presets, an instructions box). A **Report** tab lists the PDFs.
5. **`/report` skill and the summary.** `.claude/skills/report/`: preflight, check the study's age (offer `/study --refresh`), load the preset, confirm the plan, write the executive summary to the preset, build, verify. Instructions shape the summary and which sections to stress. A thread anchored to a report task handles **Generate with Claude**.
6. **Docs, verify, release.** ADR 0025 to Accepted, [CLI guide](../guides/claude-cli.md), [use cases](../guides/use-cases.md), `CHANGELOG.md`, then `scripts/bump-version.ps1 -Part minor` (1.3.0), only after every check below passes.

## Verification before the version bump
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`.
- Build a report from a real study, and open it: the selected sections are all there, in the chosen order, every sub-system has its own diagram, nothing is cut off at a page edge, and the contents links work.
- A section with no source shows as unavailable in the dialog.
- The sensitive-content check passes on every commit, and `registry/reports/` is gitignored.
