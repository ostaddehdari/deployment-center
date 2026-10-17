# ZohaOnline v0.3.7 — Source Verify Resume Hotfix

v0.3.6 completed all functional validation successfully:
- preview auth contract passed;
- real index builder contract passed;
- full contract suite passed 126/126;
- API build passed;
- Nuxt web build passed.

The installer then stopped at its own SOURCE VERIFY section before commit/push/restart because one brittle grep assertion returned non-zero.

v0.3.7 is resume-safe. It re-applies the idempotent preview patches and test alignment, reruns focused contracts, performs explicit fixed-string verification with a named PASS/FAIL message for every check, then commits only release-owned files, pushes to GitLab, and restarts API/Web.

No database migration is involved.
