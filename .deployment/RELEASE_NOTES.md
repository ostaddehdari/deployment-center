# ZohaOnline v0.3.4 — Admin Preview Auth Bridge

The real builder itself is healthy, but preview mode was still mounting the normal user `IndexRuntimePanel`. That component called the user runtime endpoint:

`/api/v1/index-runtime/schema/:contentType`

from an admin page and could receive 401 in the admin session context.

This release keeps the exact same renderer but adds admin-authenticated preview adapters:
- admin preview schema
- admin preview taxonomy options
- `IndexRuntimePanel` / `IndexPersonalSelect` admin-preview mode
- personal-term creation is disabled only inside admin preview

Normal user indexing continues to use the original user runtime routes unchanged.

The next major builder iteration will restore the full Gravity-style field toolbox in the Elements tab while keeping runtime-backed bindings and real preview.
