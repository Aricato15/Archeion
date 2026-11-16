# Studies

_Code studies of registered projects ([ADR 0019](../../docs/decisions/0019-code-studies.md))._

`/study <project>` in Archeion's session saves each study here as a dated snapshot: `<project>/<YYYY-MM-DD>-<commit7>/` with `study.json` (the model) and `notes.md` (the narrative). Snapshots are written only by `study save`, never edited, and pruned beyond `ARCHEION_STUDY_KEEP`. The project page's **Study** tab draws them.
