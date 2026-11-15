# 0011: Create the admin password in the viewer on a fresh start

- Status: Accepted (2026-11-15)
- Date: 2026-11-15
- Amends: [ADR 0002](0002-viewer-app-and-claude-feedback-loop.md) (the password is set with `set_admin_password.bat`, and `start.bat` refuses to start without one)

## Context
On a fresh start you had to run `set_admin_password.bat` before `start.bat` would launch anything. It's one more script to know about, and it happens before you've seen the app at all. Most local web tools start as usual and ask for the first credential in the browser.

## Decision
1. **`start.bat` always starts.** Without a password it says to create one in the viewer. `set_admin_password.bat` is removed.
2. **First-run setup in the viewer.** While no password exists, the login page becomes a "create the admin password" form: the password twice, at least 12 characters. Saving it logs you in.
   - `GET /api/auth/setup` says whether setup is needed. `POST /api/auth/setup` creates the password. These are the only new public endpoints.
   - The password is created only if none exists, in one transaction (`INSERT ... ON CONFLICT DO NOTHING`), so two requests can't both set it. Once one exists, setup answers 409. It never changes a password.
   - Setup is offered only while the backend listens on this machine (`ARCHEION_HOST` is a loopback address, the default). Listening more widely, anyone who reached it first could claim the account, so the password must then be set with the CLI.
   - The Origin check applies, as for every state-changing request, so another website can't submit the form.
3. **Changing or resetting the password stays with the CLI:** `scripts/archeion.ps1 password set`. It logs out every session. The login page shows the command.

## Consequences
- Between the first start and the moment you create the password, any process on this machine could create it first. That's the same trust boundary as the database file, which any process running as you can already open. On a shared machine, create the password straight after the first start.
- The rest of [ADR 0002](0002-viewer-app-and-claude-feedback-loop.md) is unchanged: one admin account, a salted scrypt hash in the database, HttpOnly session cookies, and every other endpoint behind a session.
