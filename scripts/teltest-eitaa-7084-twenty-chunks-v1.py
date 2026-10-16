#!/usr/bin/env python3
"""Unlock exactly 20 sequential chunks of the already verified video 7084.

Follow-on to deployed one-chunk patch. Gateway stays private and requires
the existing internal authorization. No sending or queue changes here.
"""
import argparse
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("chunk_route", ROOT / "teltest-eitaa-video-first-chunk-route-v1.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
h = mod.h
WEB, GATEWAY = h.WEB, h.RUNTIME
MAX_OFFSET = 19 * 524288
MARK = "// TELTEST_EITAA_VIDEO_7084_20_CHUNKS_V1"

def transform(py, js):
    h.must(mod.J_MARK in js and mod.P_MARK in py, "FIRST_CHUNK_PATCH_MISSING")
    h.must(MARK not in js, "ALREADY_EXPANDED")
    h.must("timingSafeEqual" in js and "app.listen(port, '127.0.0.1'" in js, "SECURITY_NOT_VERIFIED")
    a = "        let videoProbeUsed = false;"
    b = "Number(b.offset) === 0"
    c = "byteRef && !videoProbeUsed;"
    d = "            videoProbeUsed = true;"
    for key in (a,b,c,d):
        h.must(js.count(key) == 1, "EXPECTED_GATEWAY_GUARD_SHAPE_CHANGED")
    js = js.replace(a, """        // TELTEST_EITAA_VIDEO_7084_20_CHUNKS_V1
        // Pins the first authenticated document, advances exactly one 512-KiB chunk
        // per admission, and rejects all repeats/other files.
        let videoProbeNextOffset = 0;
        let videoProbeIdentity = null;""", 1)
    js = js.replace(b, f"(Number.isSafeInteger(Number(b.offset)) && Number(b.offset) >= 0 && Number(b.offset) <= {MAX_OFFSET} && Number(b.offset) % 524288 === 0)", 1)
    js = js.replace(c, """byteRef &&
                Number(b.offset) === videoProbeNextOffset &&
                (videoProbeIdentity === null || videoProbeIdentity === JSON.stringify([b.phone,b.id,b.access_hash,ref]));""", 1)
    js = js.replace(d, """            if (videoProbeIdentity === null) videoProbeIdentity = JSON.stringify([b.phone,b.id,b.access_hash,ref]);
            videoProbeNextOffset += 524288;""", 1)
    h.must("videoProbeUsed" not in js and MARK in js, "PATCH_NOT_COMPLETE")
    return py, js

def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    h.guard()
    with open("/run/lock/teltest-eitaa-history-route.lock", "a") as handle:
        import fcntl
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        h.guard()
        original_py = WEB.read_text(encoding="utf8")
        original_js = GATEWAY.read_text(encoding="utf8")
        new_py, new_js = transform(original_py, original_js)
        print("EITAA_POST_7084_20_CHUNK_PATCH_STAGED")
        print("MAX_ALLOWED_CHUNK_REQUESTS=20")
        print("STRICT_INCREASING_OFFSETS=YES")
        print("FIRST_DOCUMENT_ID_PINNED_IN_GATEWAY=YES")
        print("GATEWAY_AUTH_LOOPBACK_UNCHANGED=YES")
        print("JOB11_TIMERS_STILL_STOPPED=YES")
        if args.check:
            print("DRY_RUN_OK__NO_PRODUCTION_CHANGES")
            return
        import datetime, shutil
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = Path("/opt/teltest/backups/eitaa-7084-full-send") / stamp
        backup.mkdir(mode=0o700, parents=True, exist_ok=False)
        backup_js = backup / "MainExpress.ts"
        shutil.copy2(GATEWAY, backup_js)
        st = GATEWAY.stat()
        changed = False
        try:
            h.write_like(GATEWAY, new_js, st)
            changed = True
            h.must(h.run(["systemctl", "restart", "teltest-eitaa-gateway.service"], timeout=45).returncode == 0, "GATEWAY_RESTART_FAILED")
            h.must(h.check_service(), "POST_DEPLOY_HEALTH_FAILED")
            print("DEPLOY_OK=EITAA_VIDEO_7084_20_CHUNKS_V1")
            print("BACKUP=" + str(backup))
            print("TELTEST_CLIENT_UNCHANGED=YES")
            print("JOB11_TIMERS_STILL_STOPPED=YES")
        except Exception:
            if changed:
                print("ROLLBACK_STARTED")
                h.write_like(GATEWAY, original_js, st)
                h.run(["systemctl", "restart", "teltest-eitaa-gateway.service"], timeout=45)
            raise

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("SAFE_STOP_ERROR_CLASS=" + type(exc).__name__)
        if isinstance(exc,RuntimeError):
            print("SAFE_STOP_REASON=" + str(exc)[:110])
        sys.exit(1)
