# 0027: Groups with a home, and promoting a project to a group

- Status: Accepted (2026-11-19). Nothing is built yet.
- Date: 2026-11-19
- Builds on: [ADR 0006](0006-multi-project-registry.md), [ADR 0016](0016-projects-and-modules.md), [ADR 0019](0019-code-studies.md), [ADR 0022](0022-design-and-plan-a-project.md), [ADR 0026](0026-remove-a-registered-project.md)
- Would amend: [ADR 0010](0010-manage-roots-and-registration-in-the-viewer.md) (one more write to a page's frontmatter), [ADR 0019](0019-code-studies.md) (a study may be scoped to a subfolder and may be read by a group).
- Background: [the brainstorm](../notes/2026-11-19-groups-as-promoted-projects-brainstorm.md)

## Context
A group is a page with a narrative and a list of members. It has no folder, so it can't own a design, a study, a glossary, a report or an inbox. Those are all keyed by a project's name. When a system's top layer is first worked out as a project (often through `/design`) and the parts are grouped afterwards, the design stays on a placeholder project, and the project and the group of the same name coexist. A single large project also can't be split: one study of 1000+ components can't be read.

## Decision
1. **A group may have a home.** A group is virtual (as today) or has a home: a folder in a named root, and optionally its own git repository. A group with a home is managed like a project: its docs are shown as its own, and it has an inbox, a design, a glossary, a study and reports.
2. **Stored as a project page with `type: group`.** `type:` (ADR 0016) gains a third value. The page lives in `registry/projects/<name>.md` and carries the structural facts (`root`, `path`, `inbox_edits`, `status`, `ports`, `depends_on`). Members are the pages whose `group:` is that name, as today. A page in `registry/groups/<name>.md` of the same name stays optional and supplies the narrative. A virtual group is still only a `groups/` page. Everything keyed by a project name keeps working for a group with a home, because it has a project page.
3. **A name is one thing.** A group name and a project name can't differ in kind: a `groups/` page and a `projects/` page of the same name mean *one group with a home*, and any other duplicate is a warning.
4. **Promote.** `projects promote <name>` (CLI), `POST /api/registry/projects/{name}/promote` and a button on the project page set `type: group` on the page, create the `groups/` page from the template if there is none, and make the project's existing modules and sub-projects members. Nothing moves: the name, and so every study, design, thread and glossary keyed by it, stays valid. It's the same operation that merges today's duplicate pair. Promotion marks the group **needs restudy**, and `projects demote` (only for a group with no members) reverses it.
5. **No nesting.** A group's members are projects and modules, never groups. A reference from a member to another group is resolved by name: `depends_on` may name a group, links open that group's page, and the maps draw the edge between groups.
6. **Members of a break-down.** A subsystem inside the group's repository is a module (it has no `.git`), otherwise a project, by ADR 0016's detection. A study's components or sub-groups can be proposed as members, and the user confirms. Registering them writes only registry pages (ADR 0010's create-only rule), never the project.
7. **Layered studies.** A group's own study covers its top level; a member's study covers the member. A group **reads its members' latest studies rather than redoing them** and composes the flattened view from them, showing each member's snapshot date and flagging one that is older than its code. A study may be **scoped** to a subfolder (`scope` in its meta) so a module is studied without the rest of the repository.
8. **Needs restudy.** A group whose study was written before promotion keeps it, and shows *needs restudy* until a study covers it again. The restudy produces the group's snapshot and a snapshot per member from one reading pass.

## Settled questions (2026-11-19)
1. **Storage:** a `type: group` project page (point 2), with the `groups/` page optional.
2. **Inbox:** the group owns it. A module whose repository belongs to a group has the group as its owner, so `inbox --project <group>` and `--here` from the group's folder cover the group and every member. A member project with a repository of its own keeps its own inbox, and its items also appear in the group's list.
3. **Study disagreements:** the member's study wins over the group's, because it read that code more closely. The viewer shows where they differ and offers **Discuss**, which starts a thread for Archeion about it (ADR 0018) so the user can decide.
4. **Version:** the work joins 1.4.0 (still unreleased and untagged), recorded under its changelog entry.

## Alternatives considered
- **Extra project fields on the `groups/` page.** One page, but two code paths for docs, inbox and studies, and every API keyed by project would have to learn about groups.
- **A single page for both.** Cleaner, but it needs a migration of every existing group page. Point 2 leaves that for later and lets the two pages coexist.

## Consequences
- Promoting is cheap and reversible, because only the page's `type:` line and a group page change.
- The flattened view can combine snapshots of different dates, so the viewer has to say so.
- `study save` needs a multi-snapshot mode, and the scan a scope option.
- ADR 0016, point 4 (a module's owner) gains the rule in settled question 2.

## Plan
[The groups and promotion plan](../roadmap/2026-11-19-groups-and-promotion-plan.md).
