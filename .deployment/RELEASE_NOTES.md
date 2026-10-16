# ZohaOnline v0.3.3 — Runtime Overview SQL Hotfix

Browser acceptance found a 500 on:

`GET /api/admin/runtime-index/v1/overview?contentType=mold`

The PostgreSQL error is:

`column "p.taxonomy_code" must appear in the GROUP BY clause or be used in an aggregate function`

The runtime taxonomy overview query grouped by `p.sort_order`, `p.is_required`, and `p.settings`, but its ORDER BY still referenced `p.taxonomy_code`.

This release changes the assignment ordering expression to use `p.sort_order IS NULL`, which is already grouped and is a correct assignment indicator because runtime post-type field rows require a non-null sort order.

The installer also executes the exact overview SQL directly against the live PostgreSQL database before build/commit, so this class of runtime-only SQL error is covered by deployment acceptance rather than source-level tests alone.
