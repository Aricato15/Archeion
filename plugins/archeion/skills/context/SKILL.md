---
name: context
description: Show where the project this session runs in sits in the user's system of projects, as recorded in Archeion's registry - its group and the projects in it, what it depends on, what depends on it, its sub-projects, its ports and the cross-project notes. Use when the user says "/archeion:context", asks how this project relates to the others, what calls it or what it calls, or before a change that affects other projects (an API, a port, data another project reads).
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show:*)
---

# Archeion context

Archeion keeps the user's system view: a registry page for each project, recording its group, dependencies, ports and the notes that matter across projects. This skill reads the page for **the project this session runs in**. It only reads; Archeion owns the registry.

```
powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/archeion.ps1" projects show --here
```

Add `--json` for the raw facts. `--project <name>` shows another registered project, for example one this project depends on.

If the command can't find Archeion, says Archeion is too old, or says this folder isn't a registered project, tell the user. The messages say what to do, and the same fixes as in `/archeion:inbox` apply.

## Steps

1. Run `projects show --here`.
2. Give the user the short version: what the project is part of, what it depends on and what depends on it, its ports, and anything in the notes that bears on what they're doing now.
3. When a change in this session affects the projects listed under "used by" (an endpoint, a data format, a port), say so plainly. Their code is outside this project, so don't edit it.
4. If the registry disagrees with this project (a port, a dependency, its status), the registry is out of date. Offer `/archeion:report` to tell Archeion; never edit Archeion's registry from here.

## Notes

- `verified` is the date the page was last checked against the project. A page that's old or never verified may be stale.
- The facts belong to Archeion's registry, and this project's own facts (endpoints, commands) belong in its own docs. Don't copy either into the other.
