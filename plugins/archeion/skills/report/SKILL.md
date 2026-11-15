---
name: report
description: Send a change or a question from this project's session to Archeion's own inbox - a new or changed port, a new dependency, a renamed or retired project, a registry fact that's wrong, or something that affects other projects. Archeion's session then updates the registry or the system docs. Use when the user says "/archeion:report", "tell Archeion", "update the registry", or after a change in this project that the registry or other projects need to know about.
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox create:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox create:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*)
---

# Report to Archeion

Archeion owns the registry: one page per project, recording its group, dependencies, ports and cross-project notes. A project session never edits it. It sends a request to Archeion's inbox instead, and Archeion's own session (`/inbox` in Archeion) makes the change. That keeps a single owner for every fact.

```
powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" inbox create --file <path>
```

- The item goes to Archeion (`--to archeion`, the default) as a `prompt`. Use `--kind review` for feedback on the system docs as a whole.
- It records this project as its origin automatically, and shows up in the viewer marked "from <project>".
- `--to <project>` sends it to another registered project's inbox instead. Use this only when the user asks for it.

## Steps

1. Run `projects show --here`, so the report says what the registry has now and what it should say.
2. Write the report to a temporary file in your scratchpad directory, as short Markdown:
   - **What changed**, in this project, with the commit or file if there is one.
   - **What the registry says now, and what it should say**, for example `ports: [20100]` → `ports: [20105]`.
   - **Who else is affected**, from "used by", if anyone is.
3. If the user asked for the report, send it. If you're suggesting it yourself, show the text first and send it once they agree.
4. Tell the user the item number. The answer appears in the viewer, and in this session's chat only if they ask.

If the command can't find Archeion, says it's too old, or says this folder isn't registered, tell the user. The messages say what to do. Reporting works from any folder; outside a registered project, the item just has no origin.
