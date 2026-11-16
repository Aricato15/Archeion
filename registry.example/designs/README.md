# Designs

_Designs of registered projects ([ADR 0022](../../docs/decisions/0022-design-and-plan-a-project.md))._

`/design <project>` in Archeion's session, or **Ask Claude to design** on a project page's **Design** tab, works a project's design out here: `<project>/<slug>/` with `brief.md`, `architecture.md`, `plan.md`, `questions.md`, `decisions/NNNN-title.md`, `model.json` (the intended system, in the study schema, plus the ports, `depends_on`, group and kind that approval writes into the project's registry page) and a generated `design.md`. You move it through brief, architecture and plan; approving freezes `revisions/<date>-rN/`; a handoff delivers a revision to the project as a package it consumes with `/archeion:consume-design`. A design is written only by `design save`, never by hand. Example project names only, such as `example-api` ([example page](../projects/_template.md)).
