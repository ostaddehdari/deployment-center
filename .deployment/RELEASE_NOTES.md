# ZohaOnline v0.3.2 — Runtime Builder Contract Alignment

v0.3.1 successfully repaired and verified the real v0.3.0 source payload. The dedicated real-index-builder tests all passed.

The deployment then stopped in the full contract suite because two older tests still asserted the retired generic builder UI:
- Content Types was required to contain the old «نمایه پیش‌فرض» wording.
- Index Builder was required to contain the old `field-palette` generic-form palette.

Those expectations conflict with the requested architecture: the admin builder must now be runtime-backed and must not behave as the old generic Gravity-style index form builder.

v0.3.2 updates those stale contracts to verify the new real behavior:
- the three core content families have direct runtime builder links and real runtime field counts;
- the builder uses `useAdminRuntimeIndex`, collapsible Elements/Settings tabs, real term management, real `IndexRuntimePanel` preview, and runtime assign/remove/reorder/update APIs;
- the old generic `field-palette` is explicitly absent.

The installer is resume-safe for the current server state: it re-applies the verified v0.3.0 source patch, overlays the corrected contract, then runs the full suite and builds before commit/push/restart.
