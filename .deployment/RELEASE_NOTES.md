# ZohaOnline v0.3.5 — Admin Preview Prop Hotfix

v0.3.4 correctly patched the admin preview API bridge, but its source transformer missed one exact TypeScript prop declaration in `IndexPersonalSelect.vue`.

The component already referenced `props.adminPreview`, so the preview-auth test correctly stopped deployment before build/commit.

This hotfix is resume-safe for the current server state. It:
- accepts the partially applied unstaged v0.3.4 files,
- adds `adminPreview?: boolean` to the selector props,
- reruns the preview-auth contract and full suite,
- builds API and web,
- stages only the release-owned preview files,
- commits/pushes to GitLab and restarts services.

No database migration is involved.
