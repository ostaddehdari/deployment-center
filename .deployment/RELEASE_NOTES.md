# ZohaOnline v0.4.8 — Dynamic Parent Ownership Contract

v0.4.7 passed patch verification and applied both patches, then rolled back
before builds, commits, database migration, or service restart. One remaining
source contract expected the old direct `a.topic` binding; the dynamic renderer
now receives `selection(a.topic)`.

This release updates that assertion and checks the complete forwarding chain:
topic selection, dynamic field, personal selector, and separate system/personal
parent IDs. No application behavior is changed relative to the v0.4.7 candidate.
The main v0.4.4 source patch is unchanged.

Local verification uses the collected source at the exact installer base commit
`eb140a90aa78b4b92f4443a94591af415fd36392`: both patches apply cleanly, the
reported stale assertion is reproduced, and selection/filter/ownership behavior
is exercised for system parents, personal parents, single/array values, empty
values, and missing parents. The corrected complete parent contract is executed.

The collected archive is a partial source snapshot. The complete contract suite,
API build, Nuxt build, GitLab push, database backup/migration and live service
checks must still pass on the target server before installation is successful.
All existing installer gates are retained.
