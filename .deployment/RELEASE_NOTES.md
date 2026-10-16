# ZohaOnline v0.3.1

Packaging-only hotfix for v0.3.0.

The v0.3.0 source patch was correct, but one base64 character in patch-v030.part-01 was stored as lowercase h instead of uppercase H. That changed the reconstructed tar.gz checksum and stopped installation before any project file was modified.

v0.3.1 corrects that single character in the temporary release package, then verifies the original expected patch SHA256 before extraction.

No Zoha source, database, service or runtime behavior is changed by this packaging hotfix itself.
