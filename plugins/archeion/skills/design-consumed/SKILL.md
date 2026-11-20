---
name: design-consumed
description: Tell Archeion that this project consumed a design revision - it marks the design as handed off in the Design tab and reports back in the handoff thread. Reads the slug, revision and thread from the receipt that /archeion:consume-design left. Use when the user says "/archeion:design-consumed", "tell Archeion the design is consumed", or when consume-design couldn't reach Archeion and the report is still owed.
argument-hint: [slug]
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" design consumed:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" design consumed:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox:*)
---

# Tell Archeion a design was consumed

`/archeion:consume-design` writes the design into this project's docs. This skill is the part that tells Archeion, on its own, so it can be run again whenever that report didn't get through (Archeion was not found, was too old, or the command was blocked). It writes nothing in this project except an update to the receipt.

Every command goes through the plugin's launcher, exactly like this. Never call a `scripts/archeion.ps1` of Archeion's folder directly: PowerShell's execution policy blocks it, and this form is the one that's pre-approved.

```
powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" <command>
```

## Steps

1. **Find what was consumed.** Look in `.archeion/designs/` at the project's root (or its git root) for `<slug>/receipt.md`. Its top lines say `slug`, `revision`, `thread` and `reported` (`yes` or `no`).
   - With a `<slug>` argument, use that one. Several receipts and no argument: list them (slug, revision, reported) and ask which.
   - **No receipt:** if `handoff.json` is still there, the package was never consumed: say so and point to `/archeion:consume-design`. If neither exists, say there's nothing to report and **stop**.
   - A receipt with `reported: yes`: say it's already been reported, and stop unless the user asks to send it again.
2. **Project id.** `projects show --here --json`. If it says Archeion can't be found, is too old (no `design consumed`), or this folder isn't registered, tell the user what the message says and stop. The project's docs are already done.
3. **Mark it.** `design consumed <project> --slug <slug> --revision <n>`. The design becomes *handed off* in Archeion's Design tab. If this fails, show the error as it is and stop. Don't retry in another way.
4. **Report in the thread** (skip when the receipt has no `thread`):
   1. Write a short report to a scratchpad file: the revision, the files written (from the receipt, relative to this project), the decisions recorded, what's still open.
   2. `inbox create --in <thread> --claim --file <it>`, and read the new message's id from the `ids:` line.
   3. `inbox reply <id> --file <short note>`, then `inbox resolve <thread>`.
   4. If Archeion refuses because the thread's last message still waits, leave the thread and say so.
5. **Update the receipt.** Set `reported: yes` (and keep `thread`). If step 3 worked but step 4 didn't, set `reported: marked` so a later run only does the thread.
6. **Say what happened** in a line or two: marked in Archeion, thread resolved or not, and the ids.

If the user's chat shows the first command failing with an execution-policy error, the command wasn't run through the launcher above. Use it exactly as written.
