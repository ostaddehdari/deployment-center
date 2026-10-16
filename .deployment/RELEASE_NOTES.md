# ZohaOnline v0.2.0 — Embedded Runtime Indexing

This release is built from the exact live-source snapshot at GitLab commit `779929d254072f724e08b61d7cc4c1aed1bf4ac9`.

## What changes

- Runtime indexing becomes the real third step of the existing create/edit flow for all three content families: `mold`, `full_sermon`, and `supporting`.
- The indexing step is embedded in `ContentAuthoringShell`; users no longer need a separate empty indexing screen during creation.
- Create/update requests carry `IndexPayload` so content and its indexing payload are saved in one authoring request flow.
- Existing content loads its saved runtime index payload for editing.
- Topic analysis uses the approved sequence: موضوع ← کلید پردازش ← زیرموضوع ← برداشت.
- Source-backed dependent selectors are wired: جنس→ریزجنس، قالب→ریزقالب، نوع منبع→منبع.
- Personal index items remain inline, simple, and owner-only.
- Legacy UI wording «محمول» is replaced with «زیرموضوع».

## Runtime hardening

- `IndexRuntimeController` now uses the authenticated request context instead of trusting a raw `UserId` header.
- `IndexRuntimeService` uses the existing shared `DatabaseService` rather than creating a second PostgreSQL pool.
- Load/save checks real content ownership and content type.
- Personal parent terms are validated as belonging to the same owner.
- Index payload size is bounded.
- Frontend runtime API uses the existing `useZohaAuth` authenticated headers and unwraps the standard API envelope.

## Deployment safety

- No database migration is introduced by this release; the verified v0.1.3 runtime seed is required.
- The installer refuses to proceed if there are pre-staged Git changes.
- It backs up only files touched by this work.
- It runs the dedicated integration tests, the full contract suite, API build and Nuxt build before committing.
- It stages only release-owned files, pushes to the current Zoha GitLab branch, and verifies the remote SHA.
- It verifies the existing runtime database counts (40 taxonomies / 98 post-type fields / 755 terms) before restarting services.
