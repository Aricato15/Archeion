---
name: report-guided
description: Plan and build a guided PDF report of one registered project (ADR 0025): the user gives a prompt (audience, purpose, emphasis) and may give a desired structure, and Claude reads the project's sources, writes an executive summary and any other sections the prompt asks for, chooses and orders the rest, and keeps it as a plan the user reviews in the viewer before it is built. Everything Claude writes is labeled and cites the sections it came from; sourced sections are never rewritten. Use when the user says "/report-guided <project>", "write a report on <project> for <audience>", "make an executive report of <project>", or an inbox item is a report conversation. For a plain report with no prompt, use report instead.
argument-hint: <project> [--yes] ["<prompt>"]
allowed-tools: PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 report:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 report:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 projects show:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 projects show:*), PowerShell(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 study:*), Bash(powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 study:*)
---

# Guided report

A guided report follows the user's **prompt** and, if they gave one, their **outline**. You read the project's sources and draft a **plan**: an ordered list of sections, each either

- **sourced**: a catalog section (the project's docs, a study diagram, the design, the glossary, ...) that the PDF shows exactly as it is, or
- **authored**: text you wrote, labeled "Written by Claude" in the PDF, which cites the catalog sections its claims come from.

The plan is kept as a **draft** that the user reviews and edits in the viewer (the project page's **Report** button, **Guided**). They reorder, drop sections, reply in the thread, and press **Approve and build**. The standard report (`report`) is the deterministic one with no prompt; this skill is the one where you write ([ADR 0025](../../../docs/decisions/0025-project-pdf-reports.md)).

Every command runs from the repo root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 <command>
```

| Command | What it does |
|---|---|
| `projects show --project <p> --json` | the registry facts |
| `report preflight <p>` | is Edge found, is the viewer's frontend running, what has no source |
| `report catalog <p> --json` | every section a report can hold (`id`, `title`, `kind`, `available`, `reason`) |
| `report read <p> <id> [<id> ...] [--limit N]` | the content of sections as JSON: Markdown text, and for a diagram the study element it is drawn from |
| `study show <p> --json` | the whole study model, when a section's element isn't enough |
| `report plan save <p> --file <f> [--thread <n>]` | validate a plan and keep it as the draft (an authored claim without a citation is refused) |
| `report plan show <p> [--json]` | the draft, including any edits the user made in the viewer |
| `report plan discard <p>` | drop the draft |
| `report plan approve <p>` | turn the draft into a saved preset |
| `report build <p> --preset <n>` / `report verify <p> <file>` | build the PDF, and check it |

## Hard rules
- **You write only authored sections.** A sourced section is a catalog id and nothing else: never quote it into your own text as if it were the original, and never alter it. If a doc is wrong, say so in your reply, not in the report.
- **Every authored section cites at least one catalog section**, and every claim in it comes from what you read in the cited sections (`report read`), not from memory or guesswork. When the sources don't say, leave it out or say plainly that it isn't known.
- **No secrets, no absolute paths, no email addresses** in anything you write. Describe a credential by what it's for.
- **The user approves, you don't.** Don't run `report plan approve` or `report build` unless the user said to build it (in the thread, or with `--yes` in the first message). They normally press **Approve and build** in the viewer.
- **Read-only on the project**, and nothing about it goes into Archeion's committed files (ADR 0007). The plan and the PDF live in `registry/reports/<p>/` (gitignored).
- **Stay inside the scope.** If the user's message lists sections ("Use only these sections (catalog ids), and don't read or cite any others"), that is the scope: read, plan and cite only those catalog ids, for sourced and authored sections alike. Sections the user adds to the plan in the viewer later are in scope too. If the ask can't be met inside the scope (the prompt wants the risks but `study.findings` isn't listed), say so in the reply and ask, rather than reaching outside it.
- **Don't plan what has no source.** A catalog entry with `available: false` can't be in the plan; `report plan save` refuses it. Tell the user what's missing and what would fix it (a study, a design).

## Two ways to run
- **In the terminal** (`/report-guided <p> "<prompt>"`): the steps below, in one session. Ask in the terminal.
- **As a conversation** (an inbox thread anchored to a report task): the viewer's **Guided** panel starts one, and `inbox show` prints `task: a report of <p>`. Each round is one `/inbox` run, often by on-demand Claude with nobody at the terminal, so everything that carries over goes in the draft and the thread. See **Conversation mode**.

## Steps

1. **Resolve.** `projects show --project <p> --json`, and `report preflight <p>`. Problems with Edge or the frontend only block the build, not the plan: say so, and carry on planning.
2. **Understand the ask.** Take the prompt and the outline from the thread's first message (or the argument). Work out the **audience** (who reads it, what they know), the **purpose** (decide, onboard, audit, hand over), the **emphasis** (what to stress or leave out) and the **tone**. If something that changes the report a lot is unclear, ask one short question and stop for the answer; otherwise state your reading of it in the reply and go on.
3. **Scope.** Look for the list of sections at the end of the first message. With none, every available catalog section is in scope. With one, you only ever `report read` and `report plan save` those ids (and any the user adds to the plan later), and you say how the scope shapes the report if it limits it.
4. **Freshness.** `study list <p>`. If the study is behind or missing, say so in the reply and offer `/study <p> --refresh`. Plan with what exists.
5. **Read.** `report catalog <p> --json`, then `report read` the sections the ask needs. Start with the facts, the notes and the README, then the study (`study.notes`, `study.findings`, the top-level `study.map`, the interfaces), then the rest as the prompt requires. Read in batches, with `--limit` to keep it small. Note, per section, what you could use.
6. **Plan the sections.** Build the ordered list:
   - If the user gave an **outline**, follow its order and headings: each outline item becomes an authored section, a sourced section, or both (an authored introduction followed by the sourced diagram it talks about).
   - If not, open with an **executive summary** (authored, 150 to 250 words: what the project is, what it's for, how it's built, what a reader should know, the main risks), then the sourced sections that suit the audience in a sensible order, with a short authored lead-in only where it helps.
   - Sub-system diagrams (`study.sub:<id>`) come right after the map they belong to. For a technical audience include them all; for an executive one, the compact map and the findings are usually enough.
   - Keep an authored section short and plain: a few paragraphs, lists where they help, no filler. Write in the user's language and for their audience.
7. **Write the plan** to `<scratchpad>/plan.json` (below), then `report plan save <p> --file <scratchpad>/plan.json --thread <thread id>`. Fix whatever it refuses and save again.
   **A plan that isn't saved doesn't exist.** The viewer shows only what `report plan save` stored: a plan described in a reply alone gives the user nothing to review or approve. A thread anchored to a report task is always a *guided* report, however short the prompt is: never turn it into a standard report or only propose one. If the prompt is thin, assume a general reader, say so, plan anyway and save it. Check with `report plan show <p>` before you reply.
8. **Reply** (or print, in the terminal). Keep it short:
   1. your reading of the ask, in a sentence or two;
   2. the plan as a numbered list: each section's title, marked **sourced** or **written by Claude**, and why it's there;
   3. where the sources were thin, and anything you left out and why;
   4. **questions**, numbered, so the user can answer by number;
   5. that they can reorder or drop sections and press **Approve and build** in the viewer (the plan is at the top of the project page's **Reports** tab, and in the **Report** button's **Guided** panel), or reply here to change the plan.

## Conversation mode

Read the whole thread first (`inbox show <id>`), then the draft (`report plan show <p> --json`).

- **First round** (no draft yet): steps 1 to 8.
- **Next rounds**: the user replied, and may have **edited the plan in the viewer** (reordered, dropped sections). Always start from `report plan show <p> --json`, never from your memory of it. Apply their answers, keep their edits (including sections they added or took out with the checklist), and change only what they asked to change. Re-read sources only where the change needs it. Save the plan again (the thread is kept). Reply with what changed and the questions still open. Don't ask again what they already answered.
- **Build**: when the user says to build it (or `--yes` was in the first message), run `report plan approve <p>`, then `report build <p> --preset <name>`, then `report verify <p> <file>`, and reply with the file name, the page count and any problem as it is. Otherwise leave **Approve and build** to them.
- **Stop**: if they ask to drop it, run `report plan discard <p>` and say so.
- Keep each reply short. The plan is what the viewer shows.
- An on-demand run can't approve arbitrary commands. Use the report commands, read files, and write in your scratchpad. If something needs more, ask in the reply.

## The plan (`plan.json`)

```json
{
  "name": "exec-review",
  "mode": "guided",
  "title": "Example service: executive review",
  "prompt": "<the user's prompt, as they wrote it>",
  "outline": "<their outline, if any>",
  "options": {"page_size": "A4", "orientation": "portrait", "cover": true, "toc": true},
  "sections": [
    {"id": "authored:summary", "title": "Executive summary",
     "body": "Markdown, written by you.\n\n- a point the sources support",
     "cites": ["overview.facts", "study.findings"]},
    {"id": "study.map"},
    {"id": "authored:risks", "title": "What to watch", "body": "...", "cites": ["study.findings"]},
    {"id": "study.findings"}
  ]
}
```

- `name`: a short slug of letters, digits and dashes (at most 40) that says what the report is for. It becomes the preset's name.
- `title`: the report's title on the cover. Leave it empty to use the project's name.
- `prompt` and `outline`: kept with the plan, so the report can be rebuilt or revised. Copy the user's words, don't paraphrase.
- `sections`: sourced ones are `{"id": "<catalog id>"}`. Authored ones need `id` (`authored:` and a slug), `title` (at most 200 characters), `body` (Markdown, at most 20000 characters), and `cites` (catalog ids that are available). The `id`s are unique.

## Notes
- One project per run.
- The rebuild is cheap: a saved preset keeps the sections as ids, so a newer study flows into the sourced sections. Your authored text does not update itself; if the project changed a lot, plan again.
