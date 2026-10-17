# ZohaOnline v0.4.7 — Newline-Safe Contract Patch

v0.4.6 reached the contract patch validation stage but GNU git rejected the secondary patch with:
`error: corrupt patch at line 20`.

The root cause was the contract patch file ending immediately after the final hunk line with no trailing newline. The hunk counts themselves were correct.

v0.4.7 creates a fresh contract patch with a proper final newline, verifies its exact SHA256
`cbee7c6835e9578fecb9525bb7519562311d3bbba52330fd0df610c69e027228`,
then runs `git apply --check` before applying either release patch.

No project source or database changes were made by v0.4.6 because it stopped during patch validation.
