# 0015: Interactive registry maps

- Status: Accepted (2026-11-16), as part of [the code studies plan](../roadmap/2026-11-16-code-studies-plan.md)
- Date: 2026-11-15
- Builds on: [ADR 0014](0014-diagrams-for-system-design.md), [ADR 0006](0006-multi-project-registry.md)

## Context
The project maps on the Projects, group and project pages are generated from the registry frontmatter (`app/frontend/src/projects/map.ts`) as Mermaid text and rendered to a static SVG. As the registry grows this stops working well:
- Mermaid runs with `securityLevel: 'strict'`, which disables `click`, so a node can't open its project page. The cards under each map do the navigation instead.
- A large map can't be folded, filtered or searched, only scrolled.
- There is no way to highlight one project's `depends_on` and `used_by` without generating a new map.

## Decision
1. **Draw the registry maps with React Flow (`@xyflow/react`) and lay them out with `elkjs`**, in place of Mermaid. Authored diagrams in docs stay Mermaid (ADR 0014).
2. **Keep the data path.** `selectProjects()` still decides what's shown; a new builder turns that into nodes and edges instead of Mermaid text. Groups and parents become nested group nodes, `depends_on` becomes an edge, and ghost and inactive projects keep their dashed and dimmed looks.
3. **Interactions:** click a node to open its project page; hover to highlight its dependencies and dependents; fold and unfold groups and parents; zoom, pan, fit to view and a minimap. Colors follow the Mantine light and dark theme.
4. **Lazy-load it** like mermaid, so pages without a map don't download it. Layout runs in ELK's web worker, so big maps don't block the page.
5. **Tests** cover the builder with plain unit tests (as `map.test.ts` does now), and the component with a mocked layout in jsdom.

## Consequences
- Two new frontend dependencies and a change to the stack in ADR 0004.
- The maps can no longer be copied out as Mermaid text. If that's wanted, `buildMermaid` can stay as an export.
- The project cards under each map can shrink or go, once the nodes navigate.

## Before accepting
Check that React Flow and elkjs support the React version in use, measure the bundle against the current mermaid chunk, and try a map with every registered project.

## Checks (2026-11-16)
- **React:** `@xyflow/react` 12.12.0 declares `react >= 18` and runs on the React 19 in use. 13.0.0 came out the same day and isn't used yet. `elkjs` is 0.12.1. Both are pinned exactly.
- **Bundle:** React Flow is its own lazy chunk, `GraphView`, 163 kB (52 kB gzipped). The ELK engine runs in a web worker that the first graph loads (1.46 MB, about the same as the copy mermaid's ELK layout loads). The main bundle grew by about 5 kB.
- **As built:** `src/graph/` holds the generic `GraphView` (fold, hover, select, double-click to open, minimap) and its pure helpers (`graph.ts`, tested). The registry maps (`projects/map.ts: buildGraph`) and the study component maps (`study/graph.ts`, ADR 0019) both use it. `buildMermaid` stays behind a **Mermaid** toggle on every map, for copying. Double-click zoom is off, because a double click opens a node.
- **Still to do:** trying a map with every registered project is left to the user's own check in the viewer.
