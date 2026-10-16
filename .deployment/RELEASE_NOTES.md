# ZohaOnline v0.1.0 — Index Defaults & Personal Items V2

Deployment update for the existing ZohaOnline source tree. Project source remains on the user's GitLab; GitHub Deployment Center carries immutable deployment artifacts only.

Highlights:
- Default indexing model for all three content types: `mold`, `full_sermon`, `supporting`.
- Subject analysis chain: موضوع ← کلید پردازش ← زیرموضوع ← برداشت.
- UI rename of legacy «محمول» to «زیرموضوع» while preserving legacy compatibility.
- Simple private personal-term creation per user; private terms never appear to other users.
- Default taxonomy data and 16 processing keys.
- Runtime API/UI and PostgreSQL migration 170.
- Installer verifies GitLab origin and target-path cleanliness, runs tests/builds, commits and pushes source changes to the current GitLab branch, verifies remote SHA, then migrates DB and restarts services.

This is an update package for the current live ZohaOnline tree; it is not a standalone full source snapshot.
