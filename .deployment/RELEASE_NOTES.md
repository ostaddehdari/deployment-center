# ZohaOnline v0.4.2 — Payload Recovery Hotfix

v0.4.1 proved that the published internal payload bytes are stable and match SHA256, but the gzip trailer itself is invalid (CRC/ISIZE mismatch). The installer therefore stopped safely before extraction or source changes.

v0.4.2 keeps the exact same verified payload bytes and recovers the decompressed tar stream while treating the broken gzip trailer as a packaging defect. It proceeds only if:
- the reconstructed payload SHA256 matches exactly;
- a non-empty tar stream is produced;
- tar structure is valid;
- no unsafe paths are present;
- every required v0.4.0 source file exists in the recovered tar;
- dedicated hybrid-builder tests, all contracts, API build and clean Nuxt build all pass before database migration.

The server remains on the v0.3.7 GitLab base because both v0.4.0 and v0.4.1 stopped before patching/commit/migration.
