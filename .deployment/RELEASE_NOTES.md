# ZohaOnline v0.4.1 — Payload Integrity Hotfix

v0.4.0 stopped before extraction because the release manifest contained an incorrect SHA256 for the reconstructed internal payload.

The exact payload currently published in the release branch reconstructs to:

`5f2c485c7d04fe8dac4c1f6c956e0ecdd1eadda80887bc21a22217769cb44bf4`

v0.4.1 keeps the same v0.4.0 hybrid builder payload and fixes the expected internal SHA. It also adds an explicit `gzip -t` integrity test and tar listing check before any source file is touched.

The server is still on the v0.3.7 GitLab base because v0.4.0 stopped before extraction, patching, commit, migration, or restart.
