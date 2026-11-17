# 0023: Project glossaries

- Status: Accepted (2026-11-17)
- Date: 2026-11-17
- Builds on: [ADR 0006](0006-multi-project-registry.md), [ADR 0007](0007-keep-project-information-out-of-the-repo.md), [ADR 0010](0010-manage-roots-and-registration-in-the-viewer.md)

## Context
A project accumulates its own words: names of components, internal acronyms, domain jargon. Reading its docs, studies or designs gets slow when you have to stop and ask what a term means. Nothing in Archeion holds that vocabulary.

## Decision
1. **One glossary per registered project, in the private registry.** `registry/glossary/<project>.json` holds `{"terms": [{id, term, aliases, definition}]}`. It names a project's internals, so it stays out of the repo like everything else in `registry/` (ADR 0007). A module has its own glossary, like its own page.
2. **The viewer shows it on the project page's Glossary tab**, with a search box that matches the term, its aliases and its definition, ignoring case, and lists name matches first. You add, edit and delete terms there.
3. **The backend is the only writer, and only of that one file.** `services/glossary.py` validates an entry (a name and a definition, limits on length and count, a name or alias can't repeat another's, ignoring case) and replaces the file atomically. `id` is the slug of the term, so renaming a term changes its id. This is a new, narrow writer next to the ones in ADR 0010 and ADR 0022.
4. **Claude fills it through the CLI**, not by editing the file: `glossary list|set|remove <project>`. `set` adds a term or replaces the one with the same name. A study or a design session can collect a project's jargon this way.
5. **API:** `GET /api/glossary/{project}`, `POST /api/glossary/{project}`, `PUT` and `DELETE /api/glossary/{project}/{term_id}`, behind the admin session like every other route. An unregistered project is a 404.

## Consequences
- Search is done in the browser over the whole glossary. That's fine up to the limit of 2000 terms per project.
- Terms aren't linked from docs yet. Highlighting a glossary term wherever it appears in a doc or study is a later step, if it's wanted.
- A file that can't be parsed reads as an empty glossary, and the next save replaces it.
