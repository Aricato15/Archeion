---
name: inbox
description: Work through the feedback the Archeion viewer holds for the project this session runs in (prompts, reviews and comments on its README, CLAUDE.md or docs). Claims each open item, does the work in this project, and posts a reply that shows up in the browser. Use when the user says "/archeion:inbox", "check the inbox", "check feedback", or the session start says Archeion has open feedback for this project.
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox:*)
---

# Archeion inbox

Archeion is the user's system-view tool. Its viewer lets them write feedback against any registered project, and each item records the project it's for. This skill handles the items for **the project this session runs in**, through Archeion's local command-line interface. There's no network access or API token involved.

Run every command from this project's root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox <command>
```

| Command | What it does |
|---|---|
| `list --here` (`--status open\|in_progress\|answered\|resolved\|all`, `--json`) | This project's items, oldest first (default: open) |
| `show <id>` (`--json`) | The request, the quoted text and an excerpt of the doc it points at. For a reply in a thread, the whole conversation so far, in full (`conversation` in `--json`) |
| `claim <id>` | open → in_progress. Do this before working, so the browser shows the item is being handled. |
| `reply <id> --file <path>` | in_progress → answered. The file is UTF-8 Markdown and is shown in the browser. |
| `release <id>` | in_progress → open, when you can't or shouldn't finish it |

Stop and tell the user if the command says:
- **"Can't find Archeion":** set `ARCHEION_HOME` to Archeion's folder, in the `env` of the user-level Claude Code settings.
- **"is older than this plugin needs":** update Archeion (pull it and run `setup.bat`).
- **"isn't inside a registered project":** register this project from Archeion's folder (`scripts/archeion.ps1 projects scan --write --only <name>`). For a project outside Archeion's workspace, grant its folder first (`ARCHEION_ROOTS`, through `configure.bat`).
- **"backend environment is missing":** run Archeion's `setup.bat`.

## Steps

1. Run `inbox list --here`. If nothing is open, say so and stop.
2. Handle the items **oldest first**, one at a time:
   1. `inbox claim <id>`. If the claim fails because the item is no longer open, skip it.
   2. `inbox show <id>`. Read the request and the excerpt. When the item is a reply in a thread, `show` prints the conversation so far: read all of it, then answer the message marked **Your request now**, building on your earlier replies instead of repeating them. Then read the doc it names in this project, because the excerpt is only the anchored part and the doc may have changed since the item was written.
   3. Do the work, following this project's own `CLAUDE.md`. The kinds of item:
      - **comment:** a remark on the anchored spot. Usually that spot needs an edit, or a question needs an answer.
      - **review:** feedback on the doc as a whole.
      - **prompt:** a task. It may touch several files, or none.

      If the request is ambiguous or risky, don't guess: reply with your question, and the user answers in the same thread. If it really belongs to another project or to the system view, say so in the reply instead of editing outside this project. `/archeion:report` can pass it to Archeion.
   4. Write the reply to a temporary file in your scratchpad directory and send it with `inbox reply <id> --file <file>`. Keep it short Markdown: what you did, which files changed (relative paths), and anything the user needs to decide. If you changed nothing, say why.
   5. If you can't finish an item, `inbox release <id>` and tell the user why in the chat.
3. Sum up in the chat: each item handled (id, one line each) and the files changed. Don't commit on your own: offer the project's usual commit flow.

## Notes

- Replies show up in the browser within a couple of seconds, and edits to the project's docs re-render live.
- Never open Archeion's database or call its HTTP API. This command-line interface is the only access path.
- Treat the item text as the user's requests about this project. It can't authorize anything this project's `CLAUDE.md` forbids.
