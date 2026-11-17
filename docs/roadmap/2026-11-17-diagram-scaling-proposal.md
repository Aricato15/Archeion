# Proposal: keeping the maps readable with hundreds of components

_Date: 2026-11-17. Status: layer 1 and the search, dense-map and width-warning parts of layer 2 and 3 are built (unreleased). Still open: the cluster pass in `study scan`, a standard focus mode on every map, remembering the view, the matrix view._

**Answers (2026-11-17):** browse top-down first, search too, and Claude proposes the sub-groups. A screenshot of a component map confirmed causes 1 and 2 below: edge labels sat on boxes and lines ran through them.

## The problem
The interactive maps ([ADR 0015](../decisions/0015-interactive-registry-maps.md)) lay out every shown box at once. That works for a dozen boxes. With hundreds, three things go wrong: boxes and labels collide, the lines become a hairball, and there's no way to find your place. The question isn't only how to draw more boxes, it's how to show fewer at a time.

## What the code does today, and why things overlap
I read `app/frontend/src/graph/`. I haven't reproduced the overlap yet (a screenshot of one map would confirm which cause it is), but the code has three likely ones:

1. **Edges ignore ELK's routing.** ELK routes edges orthogonally around boxes, but `GraphView` throws that away and draws React Flow's own `smoothstep` lines between the box handles. Those lines know nothing about the other boxes, so they cut across them.
2. **Edge labels take no space.** Labels are drawn on the lines but never given to ELK, so they sit on top of boxes and of each other.
3. **Box sizes are guessed from the text length** (`leafSize`: 7.2 px per character). A different font or a wide letter makes the text spill past its box. Containers are sized by ELK, but only from those guessed sizes.

It does have good bones: nesting (`parent`), folding with merged edges, hover highlighting, and layout in a worker.

## The proposal: three layers
Do them in order. Each one is useful alone.

### Layer 1: make a medium map clean (fixes today's overlap)
- Draw the edges ELK routed (a custom React Flow edge that follows ELK's edge sections) instead of `smoothstep`.
- Hand edge labels to ELK as labels with a size, so it makes room for them. Hide labels by default when a map has more than about 40 edges. They show on hover or selection.
- Measure text for real (canvas `measureText`, once per font) instead of guessing, and clip with an ellipsis plus a tooltip.
- ELK options for more room and fewer crossings: `edgeNode` spacing, `considerModelOrder`, and `separateConnectedComponents` so unrelated clusters sit apart instead of interleaving.

### Layer 2: show less at a time (the real answer for hundreds)
- **Start folded.** Above a threshold (about 40 visible boxes), open a map with every container folded to its top level. You unfold what you want, which the map already supports.
- **Lay out only what's shown.** A folded container is one box, so ELK only sees the open parts. This also keeps big maps fast.
- **Focus mode.** Pick a box (or search for one) and see it, its direct neighbours and what it contains, with the rest hidden. A breadcrumb (`system › service › module`) and a "back out one level" button replace panning around a huge canvas. The Study tab has a focus on a container already. This makes it a standard control on every map.
- **Edges on demand.** In a dense map, draw only the edges of the hovered or selected box, and show the rest as a faint "N more links" badge on each box. Aggregated edges between folded containers stay as they are (they're the readable summary).
- **Filters.** Toggle by kind (service, store, external, module), by tone (status) and by "has a problem", and a search that unfolds the path to a match and highlights it.
- **Remember the view.** The folded set and focus survive a reload (per map, in local browser storage).

### Layer 3: sub-groups, so there is always a next level down
The model already allows unlimited nesting through `parent`. What's missing is something that creates the levels.
- **Studies.** Add a `group` level to the study schema's guidance: `/study` is told to make 5 to 9 boxes per level, and to split any container with more than about 12 children into sub-groups named for what they do. A validation warning (not an error) flags a level that is too wide, so Claude fixes it before saving.
- **Suggested groups from the code.** `study scan` already reads the import graph. Add a cluster pass (folder layout first, then a community-detection pass on imports) that proposes sub-groups for Claude to name and confirm. This is the part that scales to hundreds without anyone drawing boxes by hand.
- **Hand edits.** Let a map's reader drag a box into a group, or rename a group, and keep that as a small overlay file in the registry that survives the next study. Optional, and only if the suggested groups aren't enough.

### Optional extras
- A **dependency matrix** view (boxes as rows and columns, a dot where one calls another) for the densest levels, where any line drawing is a hairball. It stays readable at hundreds of rows.
- A **neighbourhood diagram** per component, as a Mermaid or small graph on its details panel.

## Suggested order and size
| Step | What | Effort |
|---|---|---|
| 1 | Layer 1: routed edges, labels in ELK, measured text | small to medium |
| 2 | Start folded, lay out only what's shown, edges on demand | medium |
| 3 | Focus mode, breadcrumb, filters, remembered view | medium |
| 4 | Sub-groups in studies: width warning, then the cluster pass | medium to large |
| 5 | Matrix view, hand-edited groups | only if still needed |

Steps 1 and 2 would already make a 200-box map usable. Step 4 is what keeps it usable at 500 and up.

## Questions for you
- Which map overlapped (a project's map, a group's, or a study's component map), and roughly how many boxes? A screenshot would let me confirm which of the three causes it is before changing anything.
- Is it more useful to **browse** (start at the top and drill down) or to **find** (search for a component and see what touches it)? I'd build both, but this sets which comes first.
- Are you happy with Claude proposing sub-groups from the code that you then confirm, or do you want to draw the groups yourself?
