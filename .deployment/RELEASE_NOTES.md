# ZohaOnline v0.1.2 — Index Defaults Packaging Fix

This hotfix addresses the packaging mismatch seen in v0.1.1.

The GitHub release lineage may contain the default index dataset as `data/index-defaults.json.gz.b64` instead of the materialized `data/index-defaults.json`. The v0.1.2 installer supports both package layouts:

- If `data/index-defaults.json` exists, it is used directly.
- If only `data/index-defaults.json.gz.b64` exists, it is decoded and gunzipped inside the temporary package before any project file is copied.
- The resulting JSON is parsed to verify that it is valid before continuing.

The installer still performs tests/builds before GitLab commit/push and database migration.
