# ZohaOnline v0.4.6 — Direct Contract Patch Verification

v0.4.5 stopped safely before backup/apply because the small contract-alignment patch had a brittle hard-coded inner SHA256 mismatch. The outer release ZIP had already passed its official SHA256 verification.

v0.4.6 removes only that fragile inner checksum for the contract patch. Safety remains stronger than needed:
- the complete official release ZIP is verified against published SHA256SUMS before extraction;
- the main v0.4.4 source patch keeps its own exact SHA256 verification;
- the contract patch must exist and must pass `git apply --check`;
- both patches are applied only after those checks;
- all focused contracts and the complete contract suite run before commit;
- API and clean Nuxt builds run before commit;
- release-owned source is automatically rolled back on any pre-commit failure;
- GitLab push, DB backup, migration 180, runtime binding counts, service restart, and Nuxt asset smoke remain mandatory.

No project/database change was made by v0.4.5 because it stopped during patch verification.
