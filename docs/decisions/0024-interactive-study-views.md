# 0024: Interactive study views, with Mermaid behind a switch

- Status: Accepted (2026-11-17)
- Date: 2026-11-17
- Builds on: [ADR 0015](0015-interactive-registry-maps.md), [ADR 0019](0019-code-studies.md), [ADR 0022](0022-design-and-plan-a-project.md)
- Amends: [ADR 0015](0015-interactive-registry-maps.md), see Decision 5.

## Context
Only the component maps were interactive (ADR 0015). The study's flows, logic, states and data were Mermaid pictures: no hover, no search, nothing to click, and the wheel scrolled the page. Large maps also overlapped: lines ran through boxes and edge labels sat on top of them.

## Decision
1. **Every study view that has a graph or a sequence is interactive by default**, and an **Interactive / Mermaid** switch (remembered in the browser) shows the Mermaid drawing instead. Both are generated from the same model, so they can't disagree.
   - Logic and states use `GraphView` (`study/graph.ts`: `activityGraph`, `stateGraph`).
   - Flows use `SequenceView` (`study/sequence.ts` lays the steps out, `study/SequenceView.tsx` draws them), because a sequence diagram isn't a graph. Hovering a participant or a message dims the rest, search dims what doesn't match, and zoom and pan come from `docs/PanZoom.tsx`.
   - The Design tab uses the same views for its components and flows.
   - Data keeps its Schema view (already interactive) and its Mermaid ER diagram.
2. **Clicking a box opens a side panel and stays on the diagram.** A flow's participant opens the component's details (with buttons to show its insides, to show it in the component map and to ask Claude), a state or step lists what leads into and out of it. Going to the component map is always an explicit button.
3. **Mermaid diagrams are interactive too**, since they're still used in docs and kept behind the switch. The wheel zooms them, dragging doesn't select text, a Find box (above the diagram, not over it) highlights and dims by label text ignoring case, and hovering a label lights every label with the same text.
4. **The maps stay readable as they grow.** Lines follow the routes ELK computes (not React Flow's straight steps), edge labels take room in the layout, and box widths are measured from the real font. Past 40 edges, labels show only on hover, and past 60 the lines stay faint until a box is hovered. Every map has a **Find a box** search that opens the boxes hiding a match and zooms to it.
5. **Component trees are shaped top-down.** `/study` and `/design` build the tree from the project's top level down, with named sub-groups of about 5 to 9 under each box. `study validate`, `study save` and `study draft save` warn (not fail) when a level holds more than 12 components. This amends ADR 0015's "every map has a Mermaid toggle": the toggle now covers every study view, not only the maps.

## Consequences
- Hover and search on Mermaid output depend on Mermaid's own class names and label elements. A Mermaid upgrade may need `docs/diagramLabels.ts` checked.
- The flow view is our own renderer, so a new kind of flow step (like a new block type) must be added to `study/sequence.ts` as well as to the Mermaid generator.
- Existing studies keep their flat trees until they're studied again (`/study <project> --refresh`).
- Still open, from [the diagram proposal](../roadmap/2026-11-17-diagram-scaling-proposal.md): a clustering pass in `study scan` that suggests sub-groups, a remembered view per map, and a dependency matrix.
