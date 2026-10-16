# TelTest production snapshot release runbook (2026-10-16)

Status: release tooling prepared; **no TelTest live-source archive has been uploaded yet**. This repository is public.

- Live host: VMID-20571, SSH 5.61.27.185:2233.
- Running code: /opt/teltest/repo; runtime database/sessions under /var/lib/teltest.
- Last proven deployed patch: TelTest Eitaa Media Exchange V1 (secure temporary media sharing).
- Native Photo V1 was delivered but its production installation has not been verified.
- Eitaa gateway remains a separately deployed and secured external dependency; it is not included.
- Delivery/scheduler timers intentionally stopped pending safe Job 11 verification.

## Release contract

A live snapshot is prepared on the source VPS using a strict allowlist and reviewed before publication to GitHub Releases under an immutable tag such as `teltest-v0.12.2-live.20261016.1`.

Assets:
- `teltest-v0.12.2-live.20261016.1.zip`: runtime Python, templates and static files.
- `install-release.sh`: pinned, backup/rollback-capable installer.
- `SHA256SUMS`: checksums for assets.
- `release-manifest.json`: individual file SHA-256 digests and dependency declaration.

Do not publish .env, accounts, SQLite, sessions, media, uploads, SSH keys, service credentials, unreviewed third-party EitaaBun code or user data.

On the actual production host, prepare snapshot and verify source manifest. Publish only after explicit review, preferably using authenticated GitHub CLI on the user's Windows workstation to avoid storing GitHub tokens on VPS. Release installers must support `--check` without touching live files and `--apply` only on the intended host; auto-delivery timers must remain off.

Important: Do not recreate a release from the older `ostaddehdari/teltest` default branch and label it as the live version; production has local patches not necessarily committed there. Do not automatically restart or reset the 250-item Eitaa transfer job.

The full helper bundle (pack_live.py, publish-teltest.sh, install-release.sh, deployctl) was generated as a conversation artifact, not yet committed here.
