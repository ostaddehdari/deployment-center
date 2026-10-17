# ZohaOnline v0.3.6 — Preview Contract Alignment

v0.3.5 successfully completed the admin-preview auth bridge itself. Its dedicated preview-auth contract passed 2/2.

Deployment stopped only because an older real-index-builder test matched an exact component prefix:

`<IndexPersonalSelect code="IDX-001"`

The correct preview-aware component now contains an additional attribute before `code`:

`<IndexPersonalSelect :admin-preview="props.adminPreview" code="IDX-001"`

v0.3.6 updates that stale assertion to verify both:
- the topic still uses the real searchable `IndexPersonalSelect` control;
- the same control receives the admin-preview flag.

This release is resume-safe for the partially applied v0.3.5 working tree, then reruns all contracts and both builds before commit/push/restart.
