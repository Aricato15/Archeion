# Registry (template)

This folder is the committed **template**. Your real registry lives in `registry/` next to it. It's gitignored, so the names, paths, ports and descriptions of your projects never reach the repo ([ADR 0007](../docs/decisions/0007-keep-project-information-out-of-the-repo.md)).

`setup.bat` copies this folder to `registry/` once, when `registry/` doesn't exist yet. After that, edit only `registry/`. The viewer shows it as the private "Registry" source, and the commit hook refuses anything under `registry/`.

```
registry/
  overview.md          the big picture: which systems exist, which services stand alone
  projects/<name>.md   one page per project or sub-project (format: projects/README.md)
  groups/<name>.md     one page per system of related projects
  interactions/        notable cross-project flows, one file each
```

Files whose name starts with `_` (like `projects/_template.md`) are examples. The registry ignores them.
