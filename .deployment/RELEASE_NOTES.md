# ZohaOnline v0.1.1 — Index Runtime Installer Hotfix

This release fixes the failed v0.1.0 installer without changing the intended index data model.

The previous attempt stopped before PostgreSQL migration and service restart because the current `apps/api/src/app.module.ts` does not have an `imports: []` property. v0.1.1 supports both NestJS module shapes: with or without an existing imports array.

The release is derived from the immutable v0.1.0 deployment package, then overlays the corrected installer logic.

Deployment order:
1. Backup affected release files.
2. Copy/index runtime files.
3. Patch AppModule safely.
4. Run dedicated and full contract tests.
5. Build API and web.
6. Commit only release-owned files.
7. Push the current Zoha branch to the existing GitLab origin and verify remote SHA.
8. Apply PostgreSQL migration 170.
9. Restart and verify `zoha-api-v3` and `zoha-web`.
10. Print database verification counts.

Unrelated pre-existing dirty files are not staged by this release.
