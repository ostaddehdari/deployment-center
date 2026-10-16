# TelTest production Eitaa media delivery — go-live boundary

This is the *existing* TelTest queue integration (not an independent 7084
smoke test). The production media patch has not been installed on VMID-20571.

## Existing production stack verified from the signed 0.12.2 live release

* `delivery_worker.py` calls `delivery_queue.process_job`.
* `process_job` processes `transfer_job_items` and dispatches Eitaa
  sources to `provider_destinations.execute_eitaa_destination` or the
  Eitaa→Telegram-user adapter.
* Eitaa account sends occur through `eitaa_live_gateway.install_provider_hook`.
* The queue's delivery session records `delivery_parts` receipts, but the
  unpatched Eitaa user-account hook bypassed that record.
* The old Eitaa media downloader queried public HTML URLs, which cannot
  return real video bytes; authenticated `messages/read/getFile` was verified
  on post 7084.

## New integration, pending deployment

* Account-authenticated, 512KiB chunked Eitaa video/audio/document downloads
  integrated in the existing provider worker.
* Existing image and text paths retained.
* Loopback-only EitaaBun API and internal key preserved with bounded, typed
  media read and file routes.
* Eitaa user-account media and text sends routed through the existing
  per-item, per-part at-most-once queue receipt journal.
* Uncertain send outcomes stay uncertain and must not be requeued.
* Long captions continue in separate ledger-tracked text messages.
* No automatic Job 11 requeue, timer restart, or prior receipt changes
  during patch deployment.

## Required before Job 11 can send the remaining posts

1. Run `scripts/teltest-job11-production-readiness-v1.py` read-only on
   VMID-20571. Inspect failed error classes, spent retry attempts, delivery
   part states, destinations, and delivery systemd timeout.
2. Reconcile previously manually posted items (7069 text, 7070 native photo,
   7072 photo document, 7084 video), only where the stored item corresponds
   to the exact channel and the user already confirmed success.
3. Never blindly call `enqueue(11)`: the current source resets attempts
   for *all* failed items, including failures whose send results may be
   ambiguous. Review pending/uncertain item states first.
4. Set a sufficient `teltest-delivery.service` execution timeout for the
   actual video upload duration, which may exceed a 45-second delivery budget.
5. Make an atomic DB backup and snapshot of live Python and gateway runtime
   prior to production rollout; publish the immutable live snapshot.
6. Deploy through a pinned GitHub commit/release, run health and queue guards,
   then enable *only* approved delivery execution. Preserve other timers and
   transfer configurations.
7. Make dashboard job status, per-item receipt and error tracking visible.
   Reconcile uncertain outcomes against destination BEFORE any manual retry.

Source is public only because the original live release is already public.
Never commit or print account tokens, sessions, private key material, or message text.
