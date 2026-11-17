# 0025: Project PDF reports

- Status: Proposed (2026-11-17)
- Date: 2026-11-17
- Builds on: [ADR 0007](0007-keep-project-information-out-of-the-repo.md), [ADR 0019](0019-code-studies.md), [ADR 0022](0022-design-and-plan-a-project.md), [ADR 0024](0024-interactive-study-views.md)
- Amends: [ADR 0013](0013-start-the-inbox-terminal-from-the-viewer.md) and [ADR 0020](0020-study-conversations-and-on-demand-claude.md), see Decision 4 (the list of processes the backend starts).

## Context
A project's facts are spread over the registry page, its docs, a study, a design and a glossary. There is no way to hand someone one document that holds all of it, with the diagrams. Reading it in the viewer works for me, not for someone who has no access to it.

## Decision
1. **A report is a PDF built from a section catalog.** `report catalog` lists what exists for a project: overview, the project's docs, the study (component map, flows, activities, data, states, interfaces, findings), the design, the glossary and the project's place in its group. A section with no source is listed as unavailable and never silently dropped.
2. **The reader chooses and orders the sections** in a dialog on the project page (a checkbox per section and per sub-system diagram, drag to reorder, page options). A choice is saved as a named **preset** per project.
3. **Diagrams are vector.** The component map is drawn compact (top level), and every sub-system (a package or module with children) is drawn as its own diagram, one level each. Flows, logic, states and the schema are drawn in full.
4. **Rendering is a print route plus headless Edge.** The frontend has a print-only route that lays out every selected section as static HTML and SVG. The backend turns it into a PDF with headless Edge (no new dependency on Windows 11) and saves it. This adds one process to the backend's list (the inbox terminal, on-demand Claude, git). The renderer gets a one-time, short-lived token, so the login requirement stays whole. The browser's own **Save as PDF** on the same route is the fallback.
5. **An instructions prompt can be added** (free text: audience, emphasis, tone, what to leave out). Instructions are used only by Claude. Giving them switches **Generate** to **Generate with Claude**, which is a thread like a study (ADR 0020).
6. **`/report <project>` is a skill.** It opens with an **executive summary** that Claude writes from the chosen sections, every claim citing a section, then adds the deterministic sections, which are built from the registry, the project's docs and the model, never from Claude's words.
7. **Reports are private** (ADR 0007). They are written only by `services/reports.py`, to `registry/reports/<project>/<date>-<preset>.pdf`, which is gitignored. A report is never copied into a project and never committed.

## Consequences
- Headless Edge must exist. `report preflight` checks for it, and the dialog says so when it's missing.
- The print route is a second way to draw the study diagrams, so a new diagram kind must be added to it as well as to the viewer.
- A report is as fresh as its study and design. The skill offers `/study --refresh` when the study is behind.
- Status moves to Accepted once the feature is built and verified in the viewer.
