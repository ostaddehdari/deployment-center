# ZohaOnline v0.4.5 — Hybrid Builder Contract Alignment

v0.4.4 successfully verified and applied the direct source patch, then ran 25 focused contracts. 24 passed and one stale contract failed before commit/migration. Automatic rollback restored all v0.4.4-owned source files.

The failing contract expected hard-coded parent mapping logic inside IndexRuntimePanel:
`code==='IDX-006'?'IDX-005'`

The v0.4.4 implementation intentionally moved dependency resolution to the runtime schema:
- IndexRuntimeService publishes `parentTaxonomyCode` using the canonical map.
- IndexRuntimePanel resolves parent values generically through `parentFor()` and `personalParentFor()`.
- IndexPersonalSelect still preserves `parentSystemTermId` / `parentUserTermId`.
- Topic/subtopic keeps its dedicated topic-analysis payload behavior.

v0.4.5 keeps the exact v0.4.4 implementation and adds only a focused contract-alignment patch for `tests/index-authoring-integration.test.cjs`.

Safety remains unchanged: direct patch SHA verification, git apply checks, source backup, automatic rollback before commit, full contract suite, API build, clean Nuxt build, source verification, GitLab push verification, DB backup, migration 180 verification, service restart and Nuxt asset smoke.
