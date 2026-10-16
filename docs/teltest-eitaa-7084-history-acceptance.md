# TelTest Eitaa post 7084 — restricted history acceptance gate

Status: PR #1 merged at e57cb20adf094a59783a8f5a10e137e5ddb11762. Production check-only at PR head c2232e59520ff49b51555f54ef2c1c6ef5c2def0 passed 3 unit tests and guarded --check. **No production apply or video download is yet confirmed.**

Scope:
- Read only up to three channel messages near post 7084 using the authenticated EitaaBun read route.
- Keep getFile disabled and do not send posts.
- Keep VMID-20571 job 11 paused and automatic delivery/scheduler timers inactive.
- A deployment must alter both /opt/teltest/repo/eitaa_live_gateway.py and the running EitaaBun runtime MainExpress.ts; the existing general deployctl ZIP installer currently does not cover the independent EitaaBun runtime.
- Stage script: scripts/teltest-eitaa-history-route-v1.py; metadata-only probe: scripts/teltest-eitaa-video-7084-probe-v1.py.
- Script performs fail-closed checks for host, gateway loopback/auth, services and queue and backs up both live files with best-effort rollback if it detects failure.
- Run --check then --apply only from pinned reviewed GitHub commit; verify outcome and send only redacted probe output.
- Once metadata is confirmed, build a new complete TelTest release bundle including its gateway dependency contract and add on-rollback provisions to deployctl before relying solely on one-command installs.
- Do not mark the video feature as working until a bounded, chunked file download has been validated as a real MP4/WebM and one actual destination post has been reconciled.
