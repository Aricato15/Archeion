# Updating Archeion and its plugin

For an install that is older than the current release. Archeion and the plugin have their own versions ([ADR 0005](../decisions/0005-semantic-versioning.md), [ADR 0009](../decisions/0009-archeion-plugin-for-project-sessions.md)), so update both. Check what you have:

- Archeion: the `VERSION` file in the repo root, or `scripts/archeion.ps1 version`.
- Plugin: `scripts/archeion.ps1 --where` (run from a project with the plugin, it prints the Archeion it found and its version), or `/plugin`.

A short how-to for each release that asks you to do something is in [`docs/updates/`](../updates/README.md): [1.3.1](../updates/update-v1.3.1.md), [1.3.2](../updates/update-v1.3.2.md) and [1.4.0](../updates/update-v1.4.0.md). What changed in each version is in [`CHANGELOG.md`](../../CHANGELOG.md) and [`plugins/archeion/CHANGELOG.md`](../../plugins/archeion/CHANGELOG.md).

## Coming from an older version: one update, not one per release

You don't need to install every release in between. Update straight to the current one: a single `git pull`, one `setup.bat`, and the database migrations run in order on the first start. The per-release notes only tell you what changed and what to look at.

| You have | Do |
|---|---|
| 1.2.0 to 1.3.x | Follow this guide once (steps 1 to 4). Update the plugin too: 1.2.0 and 1.3.0 shipped with plugin 0.3.0 or older, and 0.4.0 renames `/archeion:report` to `/archeion:notify`. The one migration (11, from 1.4.0) runs by itself, so back up the database first. |
| 1.0.0 or 1.1.0 | The same. The plugin is 0.1.x or 0.2.x, so updating it matters more (step 3). The only migration after 1.0.0 is 11 (from 1.4.0), and it runs by itself. |
| Before 1.0.0 | The same, and the migrations 6 to 11 run on first start (back up first). |
| 1.4.0 | You're current. |

The [1.4.0 note](../updates/update-v1.4.0.md) has what to check afterwards for the whole range.

## What is kept, and what is touched

| Your data | Where | Update behaviour |
|---|---|---|
| Admin password, sessions, feedback threads, runner and Claude job state | `app/backend/data/archeion.db` (gitignored) | Migrated **automatically** the first time the new backend starts. Migrations only go forward. |
| Registry pages, studies, designs | `registry/` (gitignored) | Never overwritten. Files are only read, or added by you and Claude. |
| Settings | `.env` (gitignored) | Never overwritten. A new setting just takes its default until you change it. |
| Code, docs, scripts | the git repo | Replaced by the update. |

The database is the one thing that can't be undone by going back in git, because a migration changes its schema. Back it up first.

## 1. Back up (2 minutes)

1. Stop Archeion: `stop.bat`.
2. Copy the database with SQLite's own backup, not a file copy:
   ```
   sqlite3 app/backend/data/archeion.db ".backup app/backend/data/archeion.backup.db"
   ```
   Without the `sqlite3` tool, stop Archeion and copy `archeion.db` together with `archeion.db-wal` and `archeion.db-shm` if they exist.
3. Optionally copy the `registry/` folder too. It's private and not in git, so nothing else has a copy of it.

## 2. Update Archeion

From the repo root:

```
git fetch
git checkout main
git pull
setup.bat
start.bat
```

- `setup.bat` runs `uv sync --frozen` and `npm ci`, so new or changed dependencies are installed inside the project. It leaves `registry/` and `.env` as they are, and it regenerates `.env.example`.
- On the first `start.bat`, the backend applies any database migrations by itself (`PRAGMA user_version`). You don't run anything. Your password still works, and your feedback threads and settings are kept.
- If the backend refuses to start and the log mentions a migration, restore the backup from step 1 (stop Archeion, put the backup over `app/backend/data/archeion.db`, remove any `-wal` and `-shm` next to it), go back to your old version with `git checkout <old tag or commit>`, and report it.
- If you changed files in the repo yourself, `git pull` may stop on a conflict. Stash or commit your change first.
- Settings: a new setting needs no action. To review them, run `configure.bat`.
- After a fresh clone, or if the commit hook doesn't seem to run, set `git config core.hooksPath .githooks`.

### Version notes

| Version | What to know when coming from an older one |
|---|---|
| 1.4.0 | Groups with a home, creating and removing projects from the viewer, a study that doesn't need git, the Updates tab. Back up `registry/`, which more actions now write to. Adds a setting for on-demand Claude (`--add-dir` the project's folder) and deleting a thread. **Database migration 11** (schema 10 → 11) runs by itself on first start, so back up the database. The plugin is unchanged. See the [update note](../updates/update-v1.4.0.md). |
| 1.3.2 | Edits now launches Claude in auto mode by default, diagram and Reports-tab fixes. No database migration. See the [update note](../updates/update-v1.3.2.md). |
| 1.3.1 | PDF reports (added in 1.3.0), and the plugin's `/archeion:report` is renamed `/archeion:notify` (plugin 0.4.0). `setup.bat` installs two new dependencies. No database migration. See the [update note](../updates/update-v1.3.1.md). |
| 1.2.0 | Interactive maps, flows and Mermaid diagrams, and a Glossary tab per project. A new `registry/glossary/` folder is created when the first term is saved. No database migration and no new setting. |
| 1.1.0 | Adds designs, and inbox commands that carry on a thread from a session (`inbox create --in`, `threads`, `resolve`) for plugin 0.2.0 and later. Adds `restart.bat`. No database migration and no new setting. `registry/designs/` is created the first time a design is started, so an existing registry needs no change. Approving a design is the one thing that writes to a registry page (`ports`, `depends_on`, `group`, `kind`, `status`), and only after you confirm. |
| 1.0.0 | Studies as conversations, Claude jobs, on-demand Claude, the inbox terminal. Database migrations 6 to 10 run on first start (threads, responder, Claude jobs, edit mode). Existing items reopened the old way become a "Reopened" message. |

Coming from before 1.0.0, read the intermediate changelog sections for anything else, and update in one go: the migrations run in order.

## 3. Update the plugin

The plugin lives in every registered project's Claude sessions, installed at user scope. Claude Code runs it from a cached copy per version, so an edit reaches your sessions only after a version bump and an update:

1. In any Claude Code session:
   ```
   /plugin marketplace update archeion
   ```
2. Update the plugin from `/plugin`, or from a terminal:
   ```
   claude plugin update archeion@archeion
   ```
3. Start a **new** session in each project. A running session keeps the version it started with.

The plugin finds Archeion by itself (`ARCHEION_HOME`, a registered path, or `../archeion` next to the project) and refuses to run against an Archeion older than the minimum it was built for (`$MinArcheion` in `plugins/archeion/scripts/archeion.ps1`, currently 0.4.0). If a skill says Archeion is too old, update Archeion (step 2) first.

Plugin 0.4.0 renames `/archeion:report` to `/archeion:notify`, because Archeion now has its own `/report` (a PDF of a project). Nothing else changes, and it works with the same Archeion versions as 0.3.0. A session that was open before the update keeps calling it `/archeion:report` until you open a new one, and anything of yours that mentions the old name (a note, a habit, a prompt) needs the new one.

Plugin 0.3.0 adds `/archeion:consume-design` and a start-of-session note when a design package is waiting. It works with Archeion 0.4.0 or newer. Reporting a consumed design back to Archeion needs 1.1.0 or newer, and the skill skips that step if it can't. Plugin 0.2.0 changed how `/archeion:inbox` and `/archeion:report` carry on a thread, which needs the thread commands of the inbox CLI (`inbox create --in`, `inbox resolve`) in Archeion 1.1.0 or newer (with an older one the skills work as before and say so), so update Archeion before the plugin.

## 4. Check it worked

- Open the viewer: you can log in with your existing password and your registry, studies and feedback are there.
- The version in the viewer's header shows the new version.
- In a registered project's new session, `/archeion:context` prints the project's context. `/archeion:consume-design` says "No design package here" until a design is handed off.
- Delete the backup after a few days of normal use.

## If something looks wrong

- **Locked out:** `scripts/archeion.ps1 password set` resets the password and logs out every session.
- **Port in use:** `stop.bat` first, then `start.bat`. `restart.bat` does both.
- **Plugin shows an old version:** the marketplace wasn't refreshed. Run step 3.1 again, then update, then open a new session.
