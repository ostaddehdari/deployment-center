# ZohaOnline v0.2.1 — Component Resolution Hotfix

The v0.2.0 backend, contracts, builds and GitLab deployment all passed, but browser acceptance exposed a real UI-resolution problem: the page shell and navigation rendered while nested authoring/indexing components were unresolved, producing blank content areas.

This hotfix removes reliance on Nuxt nested-component auto-import naming for the critical authoring path.

## Fixed surfaces

- New generated content
- New sermon
- New supporting content
- Edit existing content
- Content indexing page
- Legacy/direct runtime indexing route
- Embedded runtime panel
- Runtime personal selector

The release adds explicit Vue imports for:
- `ContentAuthoringShell`
- `IndexRuntimePanel`
- `IndexPersonalSelect`

It also adds a regression contract that fails if these pages return to implicit unresolved component usage.

No database migration or seed change is included.
