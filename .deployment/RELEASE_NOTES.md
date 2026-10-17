# ZohaOnline v0.4.3 — Safe TAR Recovery Hotfix

v0.4.2 confirmed that the internal payload bytes match their SHA256, but the decompressed TAR stream itself contains at least one damaged 512-byte header/block and GNU tar exits non-zero.

v0.4.3 no longer trusts GNU tar to recover the payload. It includes a dedicated safe recovery parser that:
- scans the decompressed stream on 512-byte TAR boundaries;
- accepts only headers with a valid TAR checksum;
- rejects absolute paths and parent traversal;
- skips links;
- writes only valid regular files/directories into a private temporary recovery directory;
- requires every critical v0.4.0 source file to be present and non-empty before touching the project.

After recovery, the normal v0.4 safety chain remains unchanged: dedicated contracts, full suite, API build, clean Nuxt build and source verification all run before migration 180.

The target server is still expected to be on GitLab SHA eb140a90aa78b4b92f4443a94591af415fd36392 because v0.4.0 through v0.4.2 all stopped before applying source changes.
