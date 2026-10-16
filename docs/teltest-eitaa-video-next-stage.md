# TelTest — Eitaa authenticated video transfer: next development stage

**Status (2026-10-16): planned, not installed or claimed working.**

## Proven on live VMID-20571
- TelTest and isolated, loopback-only EitaaBun gateway are operational.
- Eitaa account OTP, channel sync and dependent destination picker have been exercised.
- Eitaa to Eitaa text delivery and JPEG photo delivery are verified; native photo was confirmed by the operator.
- Job 11 is PAUSED with delivery and scheduler timers inactive; must remain so while testing.
- Latest published baseline: teltest-v0.12.2-live.20261016.1, which predates the confirmed native-photo fix.
- Prepare and publish .2 live snapshot before introducing video changes.

## Video blocker

The saved public media URL for Eitaa post 7084 returns HTTP 200 text/html. It is **not** an MP4 payload. Retrying, renaming or forwarding that URL is not safe media extraction.

## Required implementation

1. Resolve source channel to an accessible dialog within a separately authenticated Eitaa user session. Avoid assuming that public username and internal channel ID are interchangeable.
2. Use supported EitaaBun message read operations to retrieve message 7084 (test only) and inspect the *metadata schema*, sanitizing phone, token, access hash and file references before printing logs.
3. If document media metadata is returned, consume EitaaBun's file download route with the correct document ID, file reference and byte offsets. Its published controller allows document chunks; actual response and completeness must be verified before assuming support for large MP4.
4. Stream to a bounded private temporary directory. Validate header MP4 (ftyp) / WebM (EBML), total length, chunk continuity, SHA-256 and maximum size; reject HTML, zero-byte responses and partial downloads. Delete temporary files after completion.
5. Send to one owned Eitaa destination as video/document only when type checks pass. Obtain a durable message ID or reconcile destination content before marking transferred.
6. Add integration tests with mocked EitaaBun responses and a one-item, opt-in smoke test. NEVER unpause Job 11 or restart delivery timers from an installer.
7. Publish full source snapshot to a *new immutable GitHub Release tag* and deploy only with deployctl --check then explicit --apply.

## Security/operational boundaries

- Keep EitaaBun loopback-only and internally authenticated; no user token in logs.
- No production account/session database or media is to be committed to public repositories.
- Do not bundle third-party modified EitaaBun source into public artifacts without legal/license and security review.
- Fail closed on remote errors and rate limits; avoid duplicate replays and mark uncertainty instead of success if the remote send result is ambiguous.
