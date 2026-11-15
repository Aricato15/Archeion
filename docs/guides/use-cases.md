# Use cases

How the viewer, **Archeion's session** and a **project's session** work together for everyday jobs. The commands are in the [Claude CLI guide](claude-cli.md), the panel on the right.

| Who | Where | What it does |
|---|---|---|
| **You** | The viewer (browser) | Reads docs, the registry and the maps. Leaves comments, prompts and reviews. Resolves Claude's answers. |
| **Archeion's session** | `claude` started at Archeion's root | Owns the registry and the system docs. Works through Archeion's inbox with `/inbox`. Reads projects, never writes to them. |
| **A project's session** | `claude` started in a project's folder, with the Archeion plugin | Owns that project's code and docs. Works through its inbox with `/archeion:inbox`. Reports to Archeion, never edits the registry. |

Steps marked **(planned)** aren't built yet. Until they are, the step next to them says how to do the same thing today.

The examples use made-up projects: `example-api`, a service, and `example-web`, a frontend that calls it.

---

## 1. Work on a project and keep its docs registered and up to date

**Goal:** the project shows up in Archeion with correct facts, and its docs in the viewer are always current, without copying anything into Archeion.

### Once: register it
1. **Viewer, Settings:** add the folder that holds your projects as a root, if it isn't one yet. Then click **Register** next to `example-api`. This creates a stub page in `registry/projects/`.
2. **Archeion's session:** fill in the page from the real project. Today, ask: *"Read `example-api` and fill in its registry page: kind, status, ports, depends_on, group."* Claude reads the project read-only, fills in the frontmatter and sets `verified`. **(planned)** `/study example-api` does the same and lists the evidence for each field.
3. **Viewer, Projects:** check the page and the map. If something's wrong, comment on the registry page. That reaches Archeion's inbox, and `/inbox` fixes it.

### Every day: work in the project
4. **Project's session:** work as usual. When the session starts, it says whether the viewer has feedback waiting. `/archeion:context` shows how the project fits in, and `/archeion:ports` checks a port before you take one.
5. The project's `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `ROADMAP.md` and docs folder appear in the viewer **live and read-only**. Nothing is synced: whatever the project's session writes is what the viewer shows, with each doc's git history and diffs.
6. **When a structural fact changes** (a port, a dependency, the status), run `/archeion:report` in the project's session. The report reaches Archeion's inbox, `/inbox` updates the registry page, and the map follows.

```mermaid
sequenceDiagram
  actor You
  participant V as Viewer
  participant A as Archeion session
  participant P as Project session
  You->>V: Settings: add root, Register example-api
  You->>A: fill in example-api's page (planned: /study)
  A->>V: registry page + map updated
  You->>P: work on example-api
  P-->>V: its docs, live and read-only
  P->>A: /archeion:report (port changed)
  A->>V: /inbox: registry page updated
```

---

## 2. Review changes that affect other projects, from Archeion or from the project

**Goal:** when `example-api` changes something `example-web` relies on, you see it, review it, and the right session acts on it.

### The change is reported
1. **`example-api`'s session:** before changing an endpoint, `/archeion:context` lists who uses it (here `example-web`). After the change, `/archeion:report` says what changed and who's affected. If you ask, it can also send the item straight to `example-web`'s inbox (`--to example-web`).

### Review it in the viewer
2. **Feedback:** the report shows up marked *from example-api*. The header badge counts what's waiting.
3. **Projects:** `example-api`'s page shows *Used by*, and the maps show the arrows. Open the changed doc in `example-api`'s docs, and use its history to see the diff.
4. **Give feedback where it should land:**
   - A comment on `example-api`'s doc goes to `example-api`'s inbox.
   - A prompt on `example-web`'s project page goes to `example-web`'s inbox ("update the client for the new endpoint").
   - A comment on the registry or the system docs goes to Archeion's inbox.
5. **Archeion's session:** `/inbox` records the change in the registry (`depends_on`, notes, or a flow in `registry/interactions/`) and replies.

### Or review it from the project's repo
6. **`example-web`'s session:** when it starts, it says *"Archeion: 1 open feedback item for this project"*. `/archeion:inbox` shows the request with the text it quotes, does the work, and replies. `/archeion:context --project example-api` shows the other side without leaving the repo.
7. **Viewer:** read each reply under Feedback, then resolve it or reply for another round.

```mermaid
sequenceDiagram
  actor You
  participant V as Viewer
  participant API as example-api session
  participant A as Archeion session
  participant WEB as example-web session
  API->>A: /archeion:report (endpoint changed, used by example-web)
  A-->>V: shows in Feedback, "from example-api"
  You->>V: review the diff, prompt on example-web's page
  V-->>WEB: item in example-web's inbox
  WEB->>WEB: /archeion:inbox: update the client
  WEB-->>V: reply
  A->>V: /inbox: registry and notes updated
  You->>V: resolve
```

---

## 3. Start a new project from a clean slate: ideate, plan, design

**Goal:** go from an idea to a planned, designed project that Archeion knows about. There are two ways, depending on whether you want the repo first or the idea first.

### a) Start with a new repo
1. **A session at the workspace root:** `/new-project` creates the folder from the workspace template, with its own git repo and `CLAUDE.md`.
2. **Viewer, Settings:** register it. It starts with a stub page, and its docs appear in the viewer.
3. **The new project's session:** brainstorm in the terminal, where the back-and-forth is fast. Claude writes the outcome into the project itself: the spec and plan in `docs/`, decisions as ADRs in `docs/decisions/`, and `ROADMAP.md`. `/archeion:ports` gives it a free port, and `/archeion:context` shows the projects it will sit next to.
4. **Viewer:** read the plan and diagrams. Comment on passages, and `/archeion:inbox` in the project's session revises them. Repeat until you're happy with the design.
5. **Archeion's session:** fill in the page as in use case 1 (planned: `/study`), with `status: planned` until building starts.

### b) Start inside Archeion
Use this when the idea comes before the repo, or when it's mostly about how the project fits with the others.

1. **Archeion's session:** brainstorm in the terminal. Claude records the result in the private registry. A page `registry/projects/<name>.md` with `status: planned` and **no `path` yet** holds the intended group, ports and `depends_on`, and its body holds the brief: purpose, scope, how it connects to the other projects, and open questions. **(planned)** `/brainstorm <name>` guides this and keeps the brief in its own file.
2. **Viewer:** the planned project shows up on the Projects page and the maps, so you can see where it fits. Comment on the brief, and `/inbox` revises it. Repeat.
3. **When you're ready to build:** run `/new-project` from the workspace root. Then, in Archeion's session, add `path:` (and `root:`, if it's in a root) to the planned page. Don't use Register: the page already exists.
4. **The new project's session:** `/archeion:context` shows the brief. Ask Claude to turn it into the project's own `README.md`, `CLAUDE.md` and `docs/`. **(planned)** `/archeion:bootstrap` does this in one step.
5. **Archeion's session:** cut the brief down to cross-project notes, now that the project's docs hold the details. Set `status: active` once building starts, and verify the page.

```mermaid
flowchart LR
  idea([Idea]) --> choice{Repo first?}
  choice -- "yes (a)" --> np["/new-project"] --> reg[Register in Settings] --> plan[Plan in the project's session<br/>docs/, ADRs, ROADMAP.md]
  choice -- "no (b)" --> brief[Brainstorm in Archeion's session<br/>planned page + brief] --> review[Review the brief in the viewer] --> np2["/new-project"] --> link[Add path to the planned page] --> boot[Project session turns the brief<br/>into its own docs]
  plan --> loop[Comment in the viewer,<br/>/archeion:inbox revises]
  boot --> loop
  loop --> verify[Archeion verifies the page]
```
