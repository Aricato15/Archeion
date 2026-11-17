---
name: report
description: Build a standard PDF report of one registered project (ADR 0025): a deterministic document made from its registry page, docs, code study, design, glossary and place in the system, with the sections the user picks in the order they pick. Nothing in it is written by Claude. Checks that the renderer is ready, builds, and verifies the PDF. Use when the user says "/report <project>", "make a report of <project>", "generate the PDF for <project>", "build the <name> report", or wants a report with no guidance or prompt. For a report that follows a prompt or an outline, use report-guided instead.
argument-hint: <project> [--preset <name>] [--sections a,b,c] [--yes]
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 report:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 report:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 projects show:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 projects show:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 study list:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 study list:*)
---

# Standard report

A standard report is **deterministic**: the same sections in the same order give the same PDF, and no word of it is written by Claude. It is made of **sections** from the project's catalog, in the order the user chose. The PDF is built from the viewer's print page by headless Edge and saved in `registry/reports/<project>/` (private and gitignored, [ADR 0007](../../../docs/decisions/0007-keep-project-information-out-of-the-repo.md)). The viewer's **Report** button on the project page does the same thing without Claude; this skill is for doing it from a terminal. A report that follows a prompt or an outline is a different job: use `report-guided`.

Every command runs from the repo root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 <command>
```

| Command | What it does |
|---|---|
| `projects show --project <p> --json` | the registry facts: folder, type, ports, group |
| `report preflight <p> [--json]` | is Edge found, is the viewer's frontend running, which sections have no source |
| `report catalog <p> [--json]` | every section a report can hold, with `available` and the reason when it isn't |
| `report default <p> --name <n>` | a starting preset (every available section, in catalog order) as JSON |
| `report validate <p> --file <f>` | check a preset file against the catalog without saving it |
| `report preset save <p> --file <f>` / `list` / `show <p> <n>` / `delete <p> <n>` | saved presets |
| `report build <p> --preset <n>` | build the PDF (needs the viewer's frontend running) |
| `report list <p>` / `report verify <p> <file>` | the PDFs built so far, and a check of one against its build record |
| `study list <p>` | the project's study, and how many commits behind it is |

## Arguments
- `<project>`: a registered project or module (`projects list`). Exactly one per run.
- `--preset <name>`: build a saved preset as it is. Without it, start from `report default`.
- `--sections a,b,c`: only these catalog ids, in this order (see `report catalog`). Sub-system diagrams are `study.sub:<component>`.
- `--yes`: skip the confirmation in step 4.

## Hard rules
- **Nothing is written by you.** A standard report has no summary, no commentary and no authored sections. If the user wants one, say that is a guided report and offer `report-guided`.
- **Read-only on the project.** The build reads its docs through the viewer's read-only source. Never edit, run or install anything in it.
- **Nothing about the project goes into Archeion's committed files** (ADR 0007). The PDF and its build record go only to `registry/reports/`. Never commit a report, and never copy one into a project.
- **Report failures as they are.** If the build says diagrams failed, or `verify` lists problems, say so. Don't claim a report is fine without `verify`.
- **Never delete a built report** unless the user asks for that file by name.

## Steps

1. **Resolve.** `projects show --project <p> --json`. If its folder isn't available, say so: the docs sections will be missing. The registry facts, study, design and glossary still work.
2. **Preflight.** `report preflight <p>`. If it reports a problem, stop and say what to do: no Edge means set `ARCHEION_REPORT_BROWSER` in `.env` (`configure.bat`); a frontend that isn't running means start it with `start.bat`. You can't start it yourself.
3. **Freshness.** `study list <p>`. A report's diagrams are only as current as the study. If the study is behind (`commits_since` above 0) or there is none, tell the user, and offer `/study <p> --refresh` first. Don't run it unasked: it's a different job with its own confirmation.
4. **Choose the sections.**
   - With `--preset`, `report preset show <p> <name>`, and `report validate` it if the project changed since.
   - Otherwise `report default <p> --name <n> > <scratchpad>/preset.json`, then narrow or reorder it for `--sections`, or for what the user said ("just the architecture and the data").
   - Show the user the plan: the sections in order with their titles, how many diagrams and sub-system diagrams, what is unavailable and why, the page size and orientation. Wait for a yes (skip with `--yes`). When the request came from `/inbox`, this plan is your reply.
5. **Save and build.** `report validate <p> --file <preset>`, fix what it reports, `report preset save <p> --file <preset>`, then `report build <p> --preset <n>`. A big report takes under a minute.
6. **Verify.** `report verify <p> <file>` (the build runs it too). It checks the file is a whole PDF, that it has at least a page per section, and that no diagram failed to draw.
7. **Summarise** in a few lines: the file name and where it is (`registry/reports/<p>/`), the page count, the sections that were left out and why, and the viewer's project page **Reports** tab, where it can be opened or downloaded.

## Notes
- Wide diagrams get a landscape page on their own, so they stay readable. That is automatic.
- A preset keeps the sections as ids, so a rebuild later picks up a newer study. A section whose source is gone makes `report build` refuse with the reason.
- The same PDF can be made in the viewer: **Report** on the project page.
