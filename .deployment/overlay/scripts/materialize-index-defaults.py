from pathlib import Path
import base64
import gzip
import json
import sys

pkg = Path(sys.argv[1]).resolve()
plain = pkg / "data" / "index-defaults.json"
packed = pkg / "data" / "index-defaults.json.gz.b64"

if plain.exists():
    raw = plain.read_bytes()
    source = "plain"
elif packed.exists():
    encoded = b"".join(packed.read_bytes().split())
    raw = gzip.decompress(base64.b64decode(encoded))
    plain.parent.mkdir(parents=True, exist_ok=True)
    plain.write_bytes(raw)
    source = "gzip+base64"
else:
    raise SystemExit("ERROR: neither data/index-defaults.json nor data/index-defaults.json.gz.b64 exists in package")

obj = json.loads(raw.decode("utf-8"))
post_types = [x.get("code") for x in obj.get("postTypes", [])]
if post_types != ["mold", "full_sermon", "supporting"]:
    raise SystemExit(f"ERROR: unexpected postTypes in index-defaults.json: {post_types}")

terms = obj.get("terms", {})
if len(terms.get("IDX-003", [])) != 16:
    raise SystemExit("ERROR: processing keys count is not 16")

print(f"MATERIALIZE_INDEX_DEFAULTS=PASS source={source} bytes={len(raw)}")
