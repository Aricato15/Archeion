# Update to Archeion 1.3.2

**For:** Archeion 1.3.1 → **1.3.2**. The plugin is unchanged (0.4.0). It takes about two minutes.

Coming from before 1.3.1? Read [update-v1.3.1.md](update-v1.3.1.md) and the [full update guide](../guides/update_archeion_and_plugin.md) first.

## What's new

- **Diagrams stay put.** They no longer redraw by themselves on the roadmap, changelogs, guides and every other doc.
- **A guided report's plan shows under a project's Reports tab**, with Approve and build, so you don't have to open the Report dialog to find it.
- **Edits now launches Claude in auto mode.** Settings → Claude jobs → Edits has **Auto mode** (the default) and **Seek user confirmations**. Auto mode starts the inbox terminal and on-demand runs with `--permission-mode auto`, where it used to be `acceptEdits`. It needs a Claude Code version that supports that mode.
- **The guided report skill always saves a plan**, so there's something to review.

The full list is in [`CHANGELOG.md`](../../CHANGELOG.md).

## Update in steps

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

### 2. The database (nothing to do, one optional step)

The database schema goes from 10 to **11**. The new migration does nothing, so the update itself can't change or lose your data: your password, feedback, registry, studies and settings are all kept. A backup isn't required, but it's a good habit ([step 1 of the full guide](../guides/update_archeion_and_plugin.md#1-back-up-2-minutes)).

- **Fresh installs and normal upgrades:** nothing more to do.
- **If you ran a pre-release build of 1.3.2** that added a third Edits choice, your database is already at schema 11 and has one unused column. 1.3.2 opens it as it is and never reads the column. To remove it anyway, stop Archeion and run:

  ```
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\tidy-database.ps1
  start.bat
  ```

  It writes a backup next to the database (`archeion.db.pre-1.3.2.bak`, which is never overwritten), drops the column and leaves the schema version at 11. Running it again does nothing. It refuses to run while the backend is up.

### 3. The plugin and your project sessions

Nothing to do: the plugin is still 0.4.0.

## Check that it worked

- The viewer's header shows **v1.3.2**.
- Settings → Claude jobs → **Edits** shows **Auto mode** and **Seek user confirmations**.
- Start the inbox terminal or an on-demand run: the window's mode shows auto.
- A diagram on a long doc stays still while you hover or switch windows.

## If something looks wrong

| What you see | What to do |
|---|---|
| `can't start ... database schema 11 is newer than this app (10)` | The app is older than the database. Run `git pull` and `setup.bat`, then start again. |
| A terminal fails with an unknown permission mode | Your Claude Code is too old for auto mode. Update it, or choose **Seek user confirmations**. |
| `tidy-database.ps1` says the backend is running | Run `stop.bat`, then the script again. |
| Anything else | See "If something looks wrong" in the [full guide](../guides/update_archeion_and_plugin.md#if-something-looks-wrong). |
