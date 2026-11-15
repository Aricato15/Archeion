# 0014: Diagrams for system design

- Status: Accepted (2026-11-15)
- Date: 2026-11-15
- Builds on: [ADR 0004](0004-viewer-app-stack-and-layout.md) (mermaid, lazy-loaded)

## Context
Docs and the project maps are drawn with Mermaid. For system design its default output falls short: the dagre layout tangles arrows between nested boxes, and services are plain rectangles with no way to tell a database from a queue at a glance. The registry is private (ADR 0007), so whatever renders the diagrams must run locally.

## Decision
1. **Mermaid stays the one diagram format** for docs. One syntax, which GitHub and editors also render, and which Claude writes well.
2. **The viewer registers two extras** when it first loads mermaid (`app/frontend/src/docs/MermaidBlock.tsx`):
   - the **ELK layout** (`@mermaid-js/layout-elk`), chosen per diagram with `layout: elk` in its frontmatter. The generated project maps always use it.
   - **icon packs** for `architecture-beta` diagrams and flowchart icon nodes: `logos:` (`@iconify-json/logos`, products and technologies) and `mdi:` (`@iconify-json/mdi`, generic icons).
   
   Each one is a separate chunk, downloaded only by the first diagram that uses it.
3. **Rendering stays in the browser.** No online renderer (Kroki, the PlantUML server, mermaid.ink): it would send private diagrams to a third party.
4. How to write them: [Writing diagrams](../guides/diagrams.md).

## Alternatives considered
- **D2** (WASM in the browser): the nicest text syntax for architecture, but a second language and a heavy bundle. Reconsider if Mermaid with ELK still falls short.
- **Structurizr DSL, C4-PlantUML**: need Java or a rendering server.
- **LikeC4**: good architecture-as-code with React views, but its `.c4` model would be a second source of truth next to the registry frontmatter.
- **Excalidraw, draw.io**: hand-drawn diagrams, at odds with maps generated from the registry.

## Consequences
- Existing diagrams are unchanged; the extras are opt-in, except for the project maps.
- The `logos` pack is several MB, paid only by a page that uses one of its icons.
- The static project maps still have the limits of an SVG (no click-through, no folding). [ADR 0015](0015-interactive-registry-maps.md) proposes fixing that.
