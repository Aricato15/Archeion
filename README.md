# Archeion

A system-wide view of my projects: how they interact, architecture overviews and the roadmap, kept as
Markdown and Mermaid in [`docs/`](docs/README.md). It comes with a local viewer app for reading them in a
browser and sending prompts, reviews and comments to Claude.

## Viewer app
- `app/backend/`: FastAPI on `127.0.0.1:20300`. It serves `docs/`, git history, live updates and feedback.
- `app/frontend/`: React, Vite and Mantine on port 20301. The dev server proxies `/api` to the backend.

You need [uv](https://docs.astral.sh/uv/), Node.js with npm, and git. On Windows:

1. `setup.bat` installs everything inside the project (`app/backend/venv`, `app/frontend/node_modules`).
2. Optional: `configure.bat` changes ports and other settings (writes `.env`).
3. `set_admin_password.bat` sets the admin password. Only a salted hash is stored.
4. `start.bat` opens the backend and frontend windows. Then browse to `http://127.0.0.1:20301/`.
5. `stop.bat` stops both.

Feedback written in the viewer reaches Claude Code through `/inbox` in a session started in this repo.
Claude's replies and doc edits show up in the browser by themselves.

See [`CHANGELOG.md`](CHANGELOG.md) for versions and [`docs/decisions/`](docs/decisions/) for the reasons
behind the design.
