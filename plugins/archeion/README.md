# Archeion plugin

Brings Archeion into every Claude Code session you run in a registered project ([ADR 0009](../../docs/decisions/0009-archeion-plugin-for-project-sessions.md)). Nothing is copied into your projects: the plugin is installed once, at user level, and finds Archeion's command-line interface itself.

| Part | What it does |
|---|---|
| `/archeion:inbox` | Picks up the feedback written for this project in the viewer, does the work and replies |
| `/archeion:context` | Shows this project's group, what it depends on, what depends on it, its ports and notes |
| `/archeion:ports` | Lists the ports the registry records, and flags clashes, before you pick a new one |
| `/archeion:notify` | Tells Archeion about a change (a port, a dependency, a wrong fact), or asks it a question, in its own inbox. Project sessions never edit the registry. |
| `/archeion:consume-design` | Turns a design package that Archeion delivered into `.archeion/designs/` into this project's docs: the design, its decisions as ADRs, the plan in the roadmap and additions to `CLAUDE.md`. It does nothing when there's no package. |
| SessionStart hook | Says how many feedback items are waiting for this project, and when a design package is waiting. It stays silent when neither is, outside registered projects and inside Archeion. |

**Requires Archeion 0.4.0 or later.** The plugin stops with a clear message if Archeion is older.

## Install (once per machine, at user level)
In Claude Code:

```
/plugin marketplace add <path to Archeion>
/plugin install archeion@archeion
```

Or from a terminal: `claude plugin marketplace add <path to Archeion>`, then `claude plugin install archeion@archeion --scope user`.

The marketplace is Archeion's own repo (`.claude-plugin/marketplace.json`). Added at user scope, it gives every project on the machine the plugin, wherever the project lives.

- **Turning it on per project:** the plugin works in any project you enable it in. To use it only in some projects, turn it off at user level and enable it in those projects' `.claude/settings.local.json`, which is gitignored: `"enabledPlugins": { "archeion@archeion": true }`.
- **Archeion itself** turns the plugin off in its own `.claude/settings.json`, because its session uses its own `/inbox`.

## How it finds Archeion
Claude Code runs plugins from a cached copy (`~/.claude/plugins/cache/...`), not from this repo. So `scripts/archeion.ps1` looks for Archeion in this order:
1. `ARCHEION_HOME`, if set. Put it in the `env` of your user-level Claude Code settings.
2. The folder the `archeion` marketplace was added from.
3. `../archeion`, next to the current project.

`scripts/archeion.ps1 --where` prints which Archeion it found, and its version.

## Versions and updates
The plugin has its own version, in `.claude-plugin/plugin.json`, mirrored in the marketplace entry. It's separate from Archeion's `VERSION` and changes only when the plugin changes, and Claude Code uses it to spot updates. An unchanged version means an unchanged plugin, because the cached copy isn't refreshed.

When the version goes up, update:

```
/plugin marketplace update archeion
```

Then update the plugin from `/plugin`, or with `claude plugin update archeion@archeion`, and start a new session.

- **MAJOR:** a skill is removed or renamed, or the plugin needs a newer Archeion than before (the minimum in `scripts/archeion.ps1`).
- **MINOR:** a new skill or hook.
- **PATCH:** fixes and wording.

In this repo: `scripts/bump-version.ps1 -Target plugin -Part major|minor|patch` updates `plugin.json`, the marketplace entry and [`CHANGELOG.md`](CHANGELOG.md) together. The commit hook refuses changes under `plugins/archeion/` without a version change.
