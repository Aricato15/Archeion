# Update to Archeion 1.4.0

**For:** Archeion 1.3.2 → **1.4.0**. The plugin is unchanged (0.4.0). It takes about two minutes.

Coming from before 1.3.2? Read [update-v1.3.2.md](update-v1.3.2.md) first, then the [full update guide](../guides/update_archeion_and_plugin.md).

## What's new

- **Every diagram can go full screen.** The maps, the activity and state diagrams, the data schema and the flow views now have the **Full screen** button the Mermaid diagrams already had. Escape closes it.
- **You can remove a registered project.** Use **Remove** on the project's page or next to it in Settings, or `projects remove <name>` in the CLI. Only its registry page moves, to `registry/removed/` ([ADR 0026](../decisions/0026-remove-a-registered-project.md)); the project itself isn't touched, and **Restore** brings it back, and **Delete permanently** (under Settings → Previously registered) deletes it and what was kept for it.
- **A long thread has a table of contents.** A numbered panel on the right jumps to any message and marks the one you're reading. **Top** and **Latest** buttons go to the ends of the thread.

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

### 2. The database

There is **no database migration** in this release (the schema stays at 10). Your password, feedback, registry, studies and settings are left alone. A backup isn't needed, but it's a good habit ([step 1 of the full guide](../guides/update_archeion_and_plugin.md#1-back-up-2-minutes)).

### 3. The plugin and your project sessions

Nothing to do: the plugin is still 0.4.0.

## Check that it worked

- The viewer's header shows **v1.4.0**.
- A project's map has a **Full screen** button in its top right corner.
- A project's page has a **Remove** button. Don't press it unless you mean it.
- Open a thread with several messages: numbers appear on the right.

## If something looks wrong

| What you see | What to do |
|---|---|
| Remove says the project still has modules | Remove its modules first. |
| Anything else | See "If something looks wrong" in the [full guide](../guides/update_archeion_and_plugin.md#if-something-looks-wrong). |
