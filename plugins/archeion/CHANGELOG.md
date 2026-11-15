# Changelog: Archeion plugin

The plugin's own versions, separate from Archeion's ([ADR 0009](../../docs/decisions/0009-archeion-plugin-for-project-sessions.md)). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-15

Requires Archeion 0.4.0 or later.

### Added
- `/archeion:inbox`: the project's feedback from the viewer. It replaces the portable `project-inbox` skill that was kept in Archeion's `integrations/`.
- `/archeion:context`: the project's place in the system, from `projects show --here`.
- `/archeion:ports`: the ports the registry records, with clashes flagged.
- `/archeion:report`: sends a change to Archeion's inbox, marked with the project it came from.
- A SessionStart hook that announces open feedback for the project.
- `scripts/archeion.ps1`: finds Archeion (`ARCHEION_HOME`, the marketplace's folder, or `../archeion`) and checks its version.
