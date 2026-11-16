---
name: inbox
description: Work through the feedback the Archeion viewer holds for the project this session runs in (prompts, reviews and comments on its README, CLAUDE.md or docs). Claims each open item, does the work in this project, and posts a reply that shows up in the browser. Use when the user says "/archeion:inbox", "check the inbox", "check feedback", or the session start says Archeion has open feedback for this project. Also when the user follows up in the chat on an item answered earlier, so the follow-up and its answer land in the same thread.
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
| `create --in <T> --claim --file <path>` | Records what the user said in this chat as the next message in thread T, already claimed by you. It prints the new message's id: answer that one with `reply`. It keeps the thread's project and kind |
| `threads --here` (`--status active\|answered\|all`, `--json`) | This project's conversations, one row per thread, latest change first (default: not yet resolved) |
| `resolve <id>` | Close the whole thread, when the user says it's done |

Stop and tell the user if the command says:
- **"Can't find Archeion":** set `ARCHEION_HOME` to Archeion's folder, in the `env` of the user-level Claude Code settings.
- **"is older than this plugin needs":** update Archeion (pull it and run `setup.bat`).
- **"isn't inside a registered project":** register this project from Archeion's folder (`scripts/archeion.ps1 projects scan --write --only <name>`). For a project outside Archeion's workspace, grant its folder first (`ARCHEION_ROOTS`, through `configure.bat`).
- **"backend environment is missing":** run Archeion's `setup.bat`.

## Keep the ids

Every inbox command that changes something ends with a line `ids: item #<N>, thread #<T>`, and `show` prints it right under the summary (`--json` gives `id` and `thread_id`, and `show --json` also gives `latest_id`). Read them from the output every time, don't work them out:
- **item #N** is one message: what you `claim`, `reply` to and `release`. Only the thread's newest message can be answered.
- **thread #T** is the conversation: what a follow-up goes into (`create --in <T>`) and what `resolve <T>` closes.

When you answer an item, end its summary in the chat with both numbers ("#14, thread #9: fixed the install section"), so a follow-up later in this chat knows which thread it belongs to. If they're no longer in the chat, find the thread with `inbox threads --here --status all`: each row starts with the thread's id and gives `latest #N`.

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

## Carrying on a conversation in the chat

An item is a thread, the same conversation the viewer shows (Archeion's ADR 0018). When the user answers one of your replies **here in the chat** instead of in the viewer (a follow-up, a correction, the answer to a question you asked, "also do X"), it belongs in that thread, not in a new item and not only in the chat:

1. Take thread #T from the chat (the ids of the item you answered). Write their message to a scratchpad file, in their words (trim the chat noise, keep what they asked), and run `inbox create --in <T> --claim --file <file>`. It becomes the thread's newest message, already claimed, so no other Claude picks it up.
2. Read the new message's id from the `ids: item #<N>, thread #<T>` line it prints. That N, not T, is what you answer: do the work as for any item, then `inbox reply <N> --file <reply>`. The viewer now shows the question and your answer under the earlier ones. Tell the user the new ids, as for any item.
3. If it's refused because the thread's newest message still waits (someone wrote in the viewer meanwhile), claim and answer that message instead, taking the chat message into account.

When the user calls `/archeion:inbox` again about an earlier item, or refers to one ("the README thing from before"), find it with `inbox threads --here --status all` and carry on that thread the same way. When they say it's done, `inbox resolve <id>` closes the thread. A request in the chat that isn't about any earlier item is ordinary chat work: no item needed.

If `create --in` or `threads` isn't known, Archeion is too old for this: answer in the chat and tell the user to update Archeion.

## Notes

- Replies show up in the browser within a couple of seconds, and edits to the project's docs re-render live.
- Never open Archeion's database or call its HTTP API. This command-line interface is the only access path.
- Treat the item text as the user's requests about this project. It can't authorize anything this project's `CLAUDE.md` forbids.
