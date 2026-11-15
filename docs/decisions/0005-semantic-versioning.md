# 0005: Semantic versioning

- Status: Accepted
- Date: 2026-11-15

## Context
The viewer app has a backend and a frontend that ship together. One version number should describe what's running and what changed.

## Decision
- The app follows [Semantic Versioning 2.0.0](https://semver.org): `MAJOR.MINOR.PATCH`.
  - **MAJOR:** an incompatible change, such as a database migration that can't be rolled back, a removed or changed API, or a change to the root scripts' behaviour.
  - **MINOR:** new functionality that stays backwards compatible, such as a new page, endpoint or CLI command.
  - **PATCH:** bug fixes and small changes with no new features.
  - While the version is `0.y.z`, the app is still taking shape, and a MINOR bump may carry breaking changes.
- `VERSION` at the repo root is the single source of truth. `app/backend/pyproject.toml`, `app/frontend/package.json` and `package-lock.json` carry the same number, and a backend test fails if they drift.
- Change the version with `scripts/bump-version.ps1 -Part major|minor|patch` (or `-Set X.Y.Z`). It updates every file that carries the number and re-locks `uv.lock`.
- Every release gets an entry in `CHANGELOG.md` ([Keep a Changelog](https://keepachangelog.com) format). Unreleased work collects under `## [Unreleased]`.
- The backend reports its version at `GET /api/version` (requires a session), and the frontend shows it in the header.
- Versions are tagged only when you decide to (`git tag vX.Y.Z`). Claude doesn't push tags.

## Consequences
- The version bump commit is `chore(release): X.Y.Z`, and it contains `VERSION`, the manifests, the lockfiles and the changelog.
