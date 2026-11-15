---
name: ports
description: List the ports Archeion's registry records for every project, and flag ports recorded twice, so a new server or dev server gets a port that nothing else uses. Use when the user says "/archeion:ports", or before picking, adding or changing a port in this project.
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects ports:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects ports:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*)
---

# Archeion ports

```
powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects ports
```

This prints each recorded port with the projects that use it, and marks a port recorded for more than one project. Add `--json` for the raw list. `projects show --here` shows this project's own ports.

## Steps

1. Run `projects ports`, and `projects show --here` if you need this project's current ports.
2. When picking a port, follow the port rules this project's `CLAUDE.md` points to (for example a workspace's port ranges by category). Choose one that isn't in the list.
3. The registry only knows what it records. Also check this project's own config and the docs of the projects it runs next to before you commit to a port.
4. After the port changes in this project, the registry is out of date: offer `/archeion:report` to tell Archeion. Never edit the registry from here.

If the command can't find Archeion, says it's too old, or says this folder isn't registered, tell the user. The messages say what to do.
