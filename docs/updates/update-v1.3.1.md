# Update to Archeion 1.3.1

**For:** Archeion 1.2.0 or 1.3.0 → **1.3.1**, and the plugin 0.3.0 → **0.4.0**. It takes about five minutes.

Coming from before 1.2.0? Read the [full update guide](../guides/update_archeion_and_plugin.md) first. This note only covers the last step.

## What's new

- **PDF reports of a project** (1.3.0). The **Report** button on a project page makes a PDF with every diagram: **Standard** (you pick and order the sections) or **Guided** (Claude plans it from your prompt, and labels what it wrote). It needs Microsoft Edge, which Windows already has, and the viewer running.
- **`/archeion:report` is now `/archeion:notify`** (plugin 0.4.0). The old name clashed with Archeion's own `/report`. It does the same thing: tells Archeion about a change, or asks it a question.
- A small docs fix. It changes nothing for you.

The full lists are in [`CHANGELOG.md`](../../CHANGELOG.md) and the [plugin's changelog](../../plugins/archeion/CHANGELOG.md).

## Update in three steps

### 1. Update Archeion

In Archeion's folder:

```
stop.bat
git fetch
git checkout main
git pull
setup.bat
start.bat
```

- `setup.bat` installs two small new dependencies, one for the report dialog and one for talking to Edge. They go inside the project, nothing is installed globally.
- There is **no database migration** in this release. Your password, feedback, registry, studies and settings are left alone.
- A backup is not needed for this release. It's still a good habit before any update: see [step 1 of the full guide](../guides/update_archeion_and_plugin.md#1-back-up-2-minutes).

### 2. Update the plugin

In any Claude Code session:

```
/plugin marketplace update archeion
```

Then update the plugin from `/plugin`, or from a terminal:

```
claude plugin update archeion@archeion
```

### 3. Open a new session in each project

A session that was already open keeps the old plugin, so it still calls the skill `/archeion:report`. Close it and start a new one.

## Check that it worked

- The viewer's header shows **v1.3.1**.
- A project page has a **Report** button and a **Reports** tab.
- In a project's **new** session, `/archeion:notify` exists and `/archeion:report` is gone. `/archeion:context` still works.

## If something looks wrong

| What you see | What to do |
|---|---|
| The plugin still shows version 0.3.0 | The marketplace wasn't refreshed. Run step 2 again, then open a new session. |
| `/archeion:report` still appears | That session is older than the update. Open a new one. |
| The Report dialog says the frontend isn't running | Start Archeion with `start.bat`. The PDF is printed from the viewer. |
| The Report dialog says Edge wasn't found | Run `configure.bat` and set the Edge program in **ARCHEION_REPORT_BROWSER**. |
| Anything else | See "If something looks wrong" in the [full guide](../guides/update_archeion_and_plugin.md#if-something-looks-wrong). |
