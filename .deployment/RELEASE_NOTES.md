# ZohaOnline v0.4.4 — Direct Hybrid Gravity Runtime Builder

Built from the exact healthy source snapshot taken from target GitLab SHA `eb140a90aa78b4b92f4443a94591af415fd36392` (snapshot SHA256 `ae2fc00e08de67759e887ae610b0a063a36fdd48a0f90ef7caa4541cfc32700b`).

This release abandons the damaged nested v0.4.0 payload entirely. The official release ZIP contains one direct unified source patch plus `apply.sh`; there is no base64/gzip/tar payload reconstruction. The patch is verified before application with SHA256 `b80bbbdac908c434bf2db1588640db3c6fb2258bd7c668fdac8b84e379ccd58f` and `git apply --check`.

## Builder
- restores a complete 33-control Gravity-style toolbox, including searchable select;
- one collapsible left rail with Elements / Settings tabs;
- click-to-add and drag/reorder canvas;
- field label/key/help/placeholder/width/required/search/index settings;
- manual option editor;
- semantic Runtime taxonomy binding;
- Runtime option source for selectable controls;
- real Runtime term manager with search/create/edit/deactivate/reactivate;
- conditional show/hide rules;
- versioned draft and publish workflow;
- draft preview through the same operational IndexRuntimePanel renderer.

## Runtime
- published primary versioned form becomes the presentation/layout source of truth;
- runtime taxonomy/term tables remain the canonical vocabulary source;
- `IndexRuntimeService.schema()` reads the active published form and falls back to legacy runtime assignments if no published form is available;
- topic analysis retains `IDX-001 → IDX-003 → IDX-002 → IDX-004` payload semantics.

## Migration 180
- adds `searchable_select` to the allowed form input kinds;
- creates fresh published + draft versions for the three core system forms without deleting historical versions;
- seeds those versions from the current 98 runtime assignments: mold 33, full_sermon 34, supporting 31;
- stores runtime taxonomy binding metadata in each versioned field.

Deep asset upload for the generic File control and specialized relation selectors remain separate subsystem integrations; the generic renderer is present and persists JSON-compatible metadata/references.