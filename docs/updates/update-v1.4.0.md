# Update to Archeion 1.4.0

**For:** Archeion 1.3.2 → **1.4.0**. The plugin is unchanged (0.4.0). It takes about five minutes.

Coming from before 1.3.2? Read [update-v1.3.2.md](update-v1.3.2.md) first, then the [full update guide](../guides/update_archeion_and_plugin.md).

## What's new

- **Groups can have a home** ([ADR 0027](../decisions/0027-groups-with-a-home-and-promotion.md)). A group used to be a page that listed its projects. It can now also have a folder, docs, an inbox, a design and a study of its own, like a project.
  - **Promote a project to a group** with **Promote to group** on its page, or `projects promote <name>`. Only `type: group` and a time are added to its registry page, so its name, design, studies and threads stay attached, and its modules and sub-projects become its members.
  - **A group's Study tab reads its members' studies** instead of redoing them. It lists each member with the date of its study, has a **Top level / Flattened** switch, and where a member's study and the group's differ, the member's wins and **Discuss** starts a thread.
  - **Break down** on a group's page registers the folders its study points at as members: modules, or sub-projects when a folder has its own repository. `study save-set` saves a group's study and its members' together, all or none.
  - `depends_on` may name a group, and the inbox of a group covers its members.
- **You can create a project or group from Archeion** ([ADR 0028](../decisions/0028-create-a-project-from-the-viewer.md)). **New project or group** on the Projects page makes a new folder in a root you granted, with a README.md and CLAUDE.md holding your description, an optional git repository, and its registry page (planned by default). It never writes into a folder that exists. This is the one place Archeion writes outside its registry.
- **A study no longer needs git.** A module in a folder that isn't in a repository, or a project that isn't versioned, can be studied. Its staleness shows as unknown.
- **Name clashes in commits are yours to review.** If you register a project whose name is also an example name already used in Archeion's committed files (say `my-service`), a commit that touches such a line now stops with `REVIEW NEEDED` instead of blocking for good. Approve a term in `registry/reviewed-names.txt` (`name`, or `name path/to/file`) or change the line ([ADR 0007](../decisions/0007-keep-project-information-out-of-the-repo.md)). Only matters if you commit to the Archeion repo.
- **Every diagram can go full screen**, and **a long thread has a table of contents**.
- **You can remove a registered project.** Use **Remove** on the project's page or in Settings, or `projects remove <name>`. Only its registry page moves, to `registry/removed/` ([ADR 0026](../decisions/0026-remove-a-registered-project.md)); **Restore** brings it back.
- **An Updates tab** in the sidebar lists notes like this one.

The full list is in [`CHANGELOG.md`](../../CHANGELOG.md).

## Update in steps

### 1. Back up the registry

Registry pages are written in more places now (promotion, break-down, new projects), and `registry/` isn't in git. Copy the `registry/` folder somewhere safe before you start. The database needs no backup for this release, but it's a good habit ([step 1 of the full guide](../guides/update_archeion_and_plugin.md#1-back-up-2-minutes)).

### 2. Update Archeion

In Archeion's folder:

```
stop.bat
git fetch
git checkout main
git pull
setup.bat
start.bat
```

Then **reload the viewer**. If a page says a study "doesn't validate" with `meta.commit: Field required`, the old backend is still running: use `restart.bat`.

### 3. The database

There is **no database migration** in this release (the schema stays at 10). Your password, feedback, registry, studies and settings are left alone.

### 4. Projects and groups that share a name

If a project and a group have the same name (a project that began as the place to design a system, and a group made afterwards for its parts), `projects list` and the Projects page now warn about it. Fix it with `projects promote <name>`: the project becomes the group's home, and its design, studies and threads stay attached. Use `--dry-run` first to see what it does. Nothing needs doing if you have no such pair.

### 5. The plugin and your project sessions

Nothing to do: the plugin is still 0.4.0.

## Check that it worked

- The viewer's header shows **v1.4.0**.
- The Projects page has a **New project or group** button.
- A project's page has **Promote to group** (if it sits at the top and isn't a member of a group), **Remove**, and a map with a **Full screen** button.
- A group with a home shows a **Members** section with a **Break down** button, and its Study tab has a **Top level / Flattened** switch.
- Open a thread with several messages: numbers appear on the right.

## If something looks wrong

| What you see | What to do |
|---|---|
| A study "doesn't validate": `meta.commit: Field required` | The old backend is still running. Run `restart.bat`. |
| Promote says it can't | A module, a project inside another, or a member of a group can't be promoted: groups sit at the top and don't nest. The message says which. |
| Demote says the group has members | Move or remove them first. |
| New project says the folder exists | It never writes into an existing folder. Pick another name, or register the folder from Settings instead. |
| Remove says the project still has modules | Remove its modules first. |
| A group shows **needs restudy** | It was studied before it became a group. Study it again; the badge goes away once a newer study is saved. |
| Anything else | See "If something looks wrong" in the [full guide](../guides/update_archeion_and_plugin.md#if-something-looks-wrong). |

## Undo

Promotion only adds `type: group` and `promoted:` to a page. To undo it, remove those two lines, or restore the page from your backup. `projects demote <name>` does it for a group with no members. A project created from Archeion is an ordinary folder: delete it and its registry page (or use **Remove**).
