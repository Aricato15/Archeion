# 0009: Archeion plugin for project sessions, with its own version

- Status: Proposed
- Date: 2026-11-15
- Amends: [ADR 0006](0006-multi-project-registry.md) (the portable inbox skill in `integrations/`)

## Context
A Claude session working in a registered project should be able to use Archeion: pick up its feedback, see where the project sits in the system, and report changes back. Today the only piece is the `project-inbox` skill in `integrations/`. It has to be copied into a shared plugin by hand, it assumes Archeion is at `../archeion`, and nothing tells a project session that feedback is waiting.

Copying skills into each project isn't an option:
- Archeion never writes to a project (hard rule 5).
- Copies drift apart.
- A project's repo would start containing Archeion's files.

## Decision
1. **Archeion ships a plugin from its own repo, installed at user level.**
   - The repo root gets `.claude-plugin/marketplace.json`, a marketplace named `archeion` with one plugin in `plugins/archeion/`.
   - You add the marketplace and install the plugin once, at user scope:
     ```
     /plugin marketplace add <path to Archeion>
     /plugin install archeion@archeion
     ```
     Its skills are then available in every project on the machine, wherever the project lives ([ADR 0008](0008-named-project-roots.md)). Nothing is written into any project.
   - **Enabling it per project is your opt-in to feedback.** You can install the plugin enabled everywhere, or enable it only in some projects through their `.claude/settings.local.json`, which is gitignored.
   - Archeion's own `.claude/settings.json` turns the plugin off for this repo, because Archeion's session uses its own `/inbox` (`.claude/skills/inbox/`).
2. **What the plugin contains:**

   | Part | What it does |
   |---|---|
   | `skills/inbox` (`/archeion:inbox`) | The current `project-inbox`: list, claim, do, reply |
   | `skills/context` (`/archeion:context`) | This project's group, its dependencies in both directions, its ports and its registry notes |
   | `skills/ports` (`/archeion:ports`) | The ports the registry already uses, checked before a new port is picked |
   | `skills/report` (`/archeion:report`) | Sends a change, like a new port or a new dependency, to Archeion's own inbox |
   | `hooks/hooks.json` | At SessionStart, runs `inbox count --here` and announces waiting feedback |

   The CLI gains what these need: `projects show --here [--json]`, `projects ports [--json]`, `inbox create --project archeion --file <path>` (the item records which project sent it) and `version`.
3. **Project sessions read, and request changes through the inbox.**
   - A project session never edits `registry/`. To change a fact, it sends a request to Archeion's inbox, and Archeion's session makes the edit. The registry keeps a single owner.
   - The skills' `allowed-tools` pre-approve only `archeion.ps1 inbox ...` and `archeion.ps1 projects show|ports ...`, and nothing else in Archeion.
4. **Finding Archeion.** The skills locate `scripts/archeion.ps1` through `ARCHEION_HOME`, set once in the user-level Claude Code settings (`env`), with `../archeion` as the fallback. If Claude Code runs a directory marketplace from its source folder, the plugin's own location (`CLAUDE_PLUGIN_ROOT`) can replace the setting. That's checked during implementation.
5. **The plugin has its own version, separate from the app's.**
   - It follows Semantic Versioning in `plugins/archeion/.claude-plugin/plugin.json`, mirrored in the marketplace entry, with its own `plugins/archeion/CHANGELOG.md`. The app's `VERSION` ([ADR 0005](0005-semantic-versioning.md)) doesn't move it.
   - The plugin's version changes only when the plugin changes. So when you see a new plugin version, you know to update: `/plugin marketplace update archeion`, then update the plugin. Claude Code uses this version to spot updates.
   - MAJOR: a skill is removed or renamed, or the plugin needs a newer Archeion CLI than it did. MINOR: a new skill or hook. PATCH: fixes and wording.
   - The CLI it needs is stated as a minimum app version in the plugin's README. The skills check it with `archeion.ps1 version` and stop with a clear message if Archeion is too old.
   - `scripts/bump-version.ps1 -Target plugin -Part major|minor|patch` updates `plugin.json`, the marketplace entry and the plugin's changelog together. `-Target app`, the default, keeps today's behaviour.
   - **Enforced:** the pre-commit hook refuses a commit that changes files under `plugins/archeion/` without changing the plugin's version, and a test fails if `plugin.json`, the marketplace entry and the plugin's changelog disagree.
6. **Replaces `integrations/`.** Once the plugin ships, `integrations/workspace-core/skills/project-inbox/` is removed. The plan to install it into a shared workspace plugin is dropped.

## Consequences
- One install per machine gives every project Archeion's skills and a notice of waiting feedback, and nothing is copied into any project.
- The plugin's version says exactly when to update. A commit can't change the plugin without bumping it.
- The plugin is in the public repo, so it stays generic: no project names, no paths. The commit hook already checks this.
- Each release of the plugin gets a short entry in `plugins/archeion/CHANGELOG.md`, and app releases mention it when they need a newer plugin.
