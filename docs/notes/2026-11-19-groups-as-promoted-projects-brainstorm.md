# 2026-11-19: groups as promoted projects (brainstorm)

Notes from a design conversation on the branch `feat/v1.4.0-major-feature`. Nothing is built. The decision is [ADR 0027](../decisions/0027-groups-with-a-home-and-promotion.md) (Proposed) and the build plan is [the plan](../roadmap/2026-11-19-groups-and-promotion-plan.md). The wording is generic on purpose: no project is named here (hard rule 1).

## What set it off
Importing an export from another Archeion instance showed a system that exists twice: as a **project**, which holds the design, its conversation and a folder, and as a **group** of the same name, which lists the parts. The project was never a real codebase. It began as an empty project used to work out, through `/design`, a structure of projects, systems and modules. Once the user decided every component was part of one big system, a group was created and the smaller parts were added to it. The design stayed on the placeholder project, because groups can't own one.

## Today
- A group is a page in `registry/groups/` with a title and a narrative. Its members are the projects whose page says `group: <name>`. It has no folder, no design, no study, no glossary, no inbox of its own.
- Everything else is keyed by a project's name: studies, designs, glossaries, reports, the docs source and feedback.
- A study covers a whole project root. `study validate` warns when one level of the component map is wider than 12.

## Scenarios
| | Starts as | Folder or repository |
|---|---|---|
| a | A repository found or given, to analyse | Yes: a project |
| b | Several repositories to bring together | Optional: a group, possibly only a registry page |
| c | A project that must grow into smaller projects or modules, and stays the top layer of the system | Yes: promoted to a group, its own folder becomes the group's home |

The top layer may itself be a git repository, so a group can have a home.

## Positions taken
1. **Promote, don't duplicate.** In scenario c the project and the group are one thing that changes kind. Same name, so nothing already keyed by it moves. Migrating the placeholder case is the same operation. Do it as part of the feature.
2. **A promoted group is still managed like a project.** It keeps its docs (README, `CLAUDE.md`, docs folder, shown as the group's own), inbox, design, glossary and own study. Promotion adds members. Existing module children become members.
3. **Groups don't nest.** A reference from inside one group to another group is recognised by name and linked to the right group page (and drawn as a group-to-group edge on the maps).
4. **Members.** A subsystem inside the group's repository is a **module**, otherwise a **project** (ADR 0016: decided by whether it has its own `.git`). Sub-groups of components found in a study can become members, so the group lists them directly.
5. **Layered studies.** The group's own study covers its top level first and goes deeper over later iterations. When a member has a study, the group **reads that one and doesn't redo it**. The flattened view (everything, at the deepest level available) is composed from them and is the most detailed view there is.
6. **Promotion keeps the group's existing study** and marks it **needs restudy**. The restudy splits the information into the member modules and projects.

## The motivating case
Another instance holds one project with over a thousand components and a few high-level subsystems. They were grouped as sub-groups inside one study, which is unreadable. The goal: promote that project to a group, push its docs up to the group page, keep managing it like a project, and break its study into manageable pieces: a top-level study, plus a study for each subsystem.

## Consequences found while talking it through
- **Mixed snapshots.** Studies are immutable, dated and tied to a commit. A flattened view combines member snapshots from different dates, and modules of one repository may be at different commits. The view must show each member's snapshot date and flag a stale one.
- **A group needs a "needs restudy" state**, set on promotion and cleared when the group study and member studies exist.
- **Splitting at restudy is the biggest new piece.** `study save` writes one snapshot for one project today. A restudy of a group has to save the group's snapshot and one per member from one reading pass, and a module's study must read only its subfolder (path-scoped).
- **Cost.** A flattened view of 1000+ components has to load on request and fold by member by default.
- **Registry-only changes.** Archeion only registers and relinks members. It never moves code, because the backend never writes into a project.

## Questions, answered the same day
1. Storage: a `type: group` project page.
2. Inbox: the group owns it, members included.
3. Disagreeing studies: the member's wins, and the user can start a thread to discuss.
4. Version: the work joins 1.4.0.

All four are recorded in the ADR, which is Accepted.
