# Interactions

_How projects call or depend on each other._

The project maps are **generated** from the registry frontmatter (`depends_on`, `parent`, `group` in [`../projects/`](../projects/README.md)). The viewer's Projects page shows the overall map, each group page shows its group, and each project page shows the project's neighbourhood. Nothing here is drawn by hand, so a map can't drift from the pages.

Put a file in this folder for each notable flow or integration that needs more than an arrow: what calls what, with which payloads, and who owns the data. Link to each project's own API docs instead of copying them.
