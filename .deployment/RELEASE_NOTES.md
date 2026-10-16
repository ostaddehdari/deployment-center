# ZohaOnline v0.1.3 — Seed Runtime Defaults

v0.1.2 successfully built, tested, committed, pushed to GitLab, migrated the schema and restarted services, but database verification showed zero runtime fields and zero runtime terms.

Root cause: the lean deployment package intentionally separated schema DDL from seed generation. The versioned file `scripts/seed-index-runtime.py` was present in the package but the installer never executed it.

v0.1.3:
- materializes the default JSON;
- copies and commits the seed generator into the Zoha GitLab source tree;
- reapplies the idempotent schema migration;
- generates SQL from the versioned JSON and executes it transactionally;
- verifies 40 taxonomies;
- verifies post-type runtime fields: mold=33, full_sermon=34, supporting=31;
- verifies processing keys (IDX-003)=16;
- refuses to print PASS if any verification differs.
