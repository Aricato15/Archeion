---
name: report
description: Send a change or a question from this project's session to Archeion's own inbox - a new or changed port, a new dependency, a renamed or retired project, a registry fact that's wrong, or something that affects other projects. A report on something already reported, or an answer to Archeion's reply, carries on that conversation instead of starting a new one. Archeion's session then updates the registry or the system docs. Use when the user says "/archeion:report", "tell Archeion", "update the registry", or after a change in this project that the registry or other projects need to know about.
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*)
---

# Report to Archeion

Archeion owns the registry: one page per project, recording its group, dependencies, ports and cross-project notes. A project session never edits it. It sends a request to Archeion's inbox instead, and Archeion's own session (`/inbox` in Archeion) makes the change. That keeps a single owner for every fact.

A report is a **conversation**, the same thread the viewer shows (Archeion's ADR 0018): Archeion answers, and a follow-up from this session goes under that answer, as a reply typed in the viewer would. Archeion then reads the whole conversation, not just the newest message. Don't start a new thread for something an earlier report is already about.

```
powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox <command>
```

| Command | What it does |
|---|---|
| `threads --from-here` (`--status active\|open\|answered\|resolved\|all`, `--json`) | The threads this project started, latest change first, with each one's status, size, newest message and last reply (default: not yet resolved) |
| `show <id>` | One message. On a thread's newest message, the whole conversation so far |
| `create --file <path>` | A new thread for Archeion (`--to archeion`, the default) as a `prompt`. `--kind review` for feedback on the system docs as a whole. `--to <project>` sends it to another registered project's inbox instead; use it only when the user asks |
| `create --in <id> --file <path>` | The next message in the thread `<id>` is in. It keeps the thread's project and kind. Refused while the thread's newest message still waits for Archeion |
| `resolve <id>` | Close the whole thread, when the user says the matter is settled |

Every item records this project as its origin and shows up in the viewer marked "from <project>".

## Keep the ids

Every thread command ends with a line `ids: item #<N>, thread #<T>` (or gives `id` and `thread_id` with `--json`). These two numbers are what the conversation runs on, so read them from the output every time and don't guess them:
- **thread #T** is the conversation. A follow-up always goes in with `create --in <T>`. `resolve <T>` closes it.
- **item #N** is one message. `show <N>` on the thread's newest message prints the whole conversation.

Say both in your message to the user ("Sent to Archeion as item #12 in thread #9"), so they stay in this chat and a later `/archeion:report` in this session can carry on thread #9 without a lookup. If the ids are no longer in the chat (a new session, or the chat was summarized), find the thread with `inbox threads --from-here --status all`: each row starts with the thread's id and gives its newest message as `latest #N`.

## Steps

1. If this chat already names a thread from an earlier report ("thread #T"), and the new report is about the same matter, use that thread. Otherwise run `inbox threads --from-here`. If one of the threads is about the same change or question, or the user is answering what Archeion replied, this report **carries on that thread**. Read it with `inbox show <latest id>` first, so the new message builds on what was said and doesn't repeat it. If several could fit and it isn't clear which, ask the user.
2. For a new thread, run `projects show --here`, so the report says what the registry has now and what it should say.
3. Write the message to a temporary file in your scratchpad directory, as short Markdown:
   - A new thread: **What changed** in this project (with the commit or file, if there is one); **what the registry says now, and what it should say**, for example `ports: [20100]` → `ports: [20105]`; and **who else is affected**, from "used by", if anyone is.
   - A follow-up: only what's new, the answer to Archeion's question, or what's still wrong with its last answer.
4. If the user asked for the report, send it: `create --file <file>` for a new thread, `create --in <T> --file <file>` for a follow-up in thread T. Read the `ids:` line it prints. If you're suggesting it yourself, show the text first and send it once they agree.
   - If the follow-up is refused because Archeion hasn't answered the previous message yet, don't start a new thread. Tell the user: they can wait for the answer, or add to the waiting message by editing it in the viewer.
5. Tell the user the item and thread numbers from that line. The answer appears in the viewer. When the user asks what Archeion said, run `inbox threads --from-here` (or `show <T> --json`, whose `latest_id` is the newest message), `inbox show` that newest message and sum it up. When they say it's settled, `inbox resolve <T>`.

## When the build departs from a design

If this project was handed a design (a `receipt.md` in `.archeion/designs/<slug>/` names its revision and the files it wrote), and the change in this session goes against it (a different endpoint, port, dependency or data shape than the design said, or a decision the design made that no longer holds), say so in the report: name the design (`<slug>`) and its revision, what the design said and what the project does now, and why. Archeion's session then updates the design or the registry. That's how the design stays true instead of silently going stale.

If the command can't find Archeion, says it's too old, or says this folder isn't registered, tell the user. The messages say what to do. If it doesn't know `threads` or `--in`, Archeion is too old for conversations from a session: report as a new item, mention the earlier item number in the text, and tell the user to update Archeion. Reporting works from any folder; outside a registered project, the item just has no origin and `threads --from-here` doesn't apply.
