# 0015: Interactive registry maps

- Status: Proposed (2026-11-15)
- Date: 2026-11-15
- Builds on: [ADR 0014](0014-diagrams-for-system-design.md), [ADR 0006](0006-multi-project-registry.md)

## Context
The project maps on the Projects, group and project pages are generated from the registry frontmatter (`app/frontend/src/projects/map.ts`) as Mermaid text and rendered to a static SVG. As the registry grows this stops working well:
- Mermaid runs with `securityLevel: 'strict'`, which disables `click`, so a node can't open its project page. The cards under each map do the navigation instead.
- A large map can't be folded, filtered or searched, only scrolled.
- There is no way to highlight one project's `depends_on` and `used_by` without generating a new map.

## Decision (proposed)
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
