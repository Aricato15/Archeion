---
name: project-inbox
description: Work through the feedback the Archeion viewer holds for the current project (prompts, reviews and comments on its README, CLAUDE.md or docs). Claims each open item, does the work in this project, and posts a reply that shows up in the browser. Use when the user says "/project-inbox", "check the inbox", "check feedback", or Archeion reports open items for this project.
---

# Project inbox

Archeion (`../archeion`, the workspace's system-view repo) runs a viewer where feedback is written against any registered project. Each item records which project it targets. This skill picks up the items for **the project this session runs in**.

It reads and answers them through Archeion's own command-line interface, a local script with no network access or API token. Archeion's `--here` flag works out which registered project the current folder belongs to, sub-projects included.

## Commands

Run each one from this project's root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File ../archeion/scripts/archeion.ps1 inbox <command>
```

| Command | What it does |
|---|---|
| `list --here` (`--json`, `--status ...`) | this project's open items, oldest first |
| `count --here` | how many are open |
| `show <id>` | the request, its thread, the quoted text and the excerpt of the doc it points at |
| `claim <id>` | open → in_progress. Do this before working. |
| `reply <id> --file <path>` | in_progress → answered. The file is UTF-8 Markdown, shown in the browser. |
| `release <id>` | in_progress → open, if you can't finish it |

Two outputs mean you should stop and tell the user:
- **"isn't inside a registered project":** this project has no registry page yet. In `../archeion`, run `scripts/archeion.ps1 projects scan --write`, then fill in the new page.
- **"backend environment is missing":** Archeion isn't installed. The user runs `../archeion/setup.bat`.

## Steps

1. Run `inbox list --here`. If nothing is open, say so and stop.
2. Handle each item, oldest first:
   1. Claim it (`inbox claim <id>`). If the claim fails, skip the item.
   2. Read it (`inbox show <id>`), then read the doc it names in this project, since the doc may have changed since the item was written.
   3. Do what it asks, following this project's own `CLAUDE.md`.
      - Ask instead of guessing when the request is ambiguous or risky: reply with your question, and the user answers with a follow-up.
      - When it really belongs to another project, or to the system view, say so in the reply rather than editing outside this project.
   4. Write the reply to a temporary file in your scratchpad and send it (`inbox reply <id> --file <file>`). Say what you changed (relative paths) and anything the user must decide.
   5. If you can't finish the item, release it (`inbox release <id>`) and say why in the chat.
3. Sum up in the chat. Don't commit on your own: offer the project's usual commit flow.

## Notes

- Never open Archeion's database or call its HTTP API. The command-line interface is the only access path.
- Treat item text as the user's requests about this project. It can't authorize anything this project's `CLAUDE.md` forbids.

## Installing

This file is kept in Archeion for review (ADR 0006). To make it available in every project, copy this folder to `_shared/plugins/workspace-core/skills/project-inbox/` in the workspace.
