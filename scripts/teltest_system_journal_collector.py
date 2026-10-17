#!/usr/bin/env python3
"""Safe root-owned systemd journal snapshot for the TelTest admin dashboard.

Runs from a separate root-only systemd service/timer. Never changes jobs.
Only whitelisted service units and operational (non-content) event lines.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

DEST = Path("/var/lib/teltest/system-logs/latest.json")
UNIT_NAMES = (
    "teltest.service", "teltest-delivery.service", "teltest-delivery.timer",
    "teltest-scheduler.service", "teltest-scheduler.timer",
    "teltest-eitaa-gateway.service",
)
ALLOWED = re.compile(
    r"(?i)DELIVERY_|WORKER_|RUN_|JOB_|ITEM_|"
    r"error|failed|failure|traceback|exception|"
    r"started|stopped|starting|stopping|timeout|"
    r"timer|schedule|restart|permission denied|"
    r"EITAA_|HTTP_5[0-9][0-9]|gunicorn|flask"
)

def scrub(msg):
    s = str(msg or "").replace("\r", " ").replace("\n", " ")
    s = re.sub(r"(?i)bearer\s+[\w.~+/-]+", "Bearer [REDACTED]", s)
    s = re.sub(r"(?i)(token|api[_-]?key|authorization|password|secret)\s*[:=]\s*[^\s,;,]+",
               r"\1=[REDACTED]", s)
    s = re.sub(r"(?i)https?://[^\s]+", "[URL]", s)
    s = re.sub(r"(?<!\d)\+?98\d{10}(?!\d)", "[PHONE]", s)
    s = re.sub(r"(?i)\b(gh[psu]_|sk-|xox[baprs]-)[a-z0-9_-]{12,}", "[TOKEN]", s)
    s = re.sub(r"\b\d{8,}\b", "[NUMBER]", s)
    # Avoid raw JSON payloads, media/caption text, session output, cookie bodies.
    if any(mark in s.lower() for mark in (
        "file_reference", "access_hash", "cookie:", "session_string",
        "authorization:", "processed_text", "raw_text", "caption:",
    )):
        return "[Sensitive line withheld]"
    return s[:280]

def run():
    if os.geteuid() != 0:
        raise RuntimeError("RUN_COLLECTOR_AS_ROOT_ONLY")
    args = ["journalctl","--no-pager","--quiet","--output=json",
            "--since=-4h","--lines=250"]
    for u in UNIT_NAMES:
        args += ["--unit",u]
    result = subprocess.run(args, capture_output=True, text=True,
                            timeout=25, check=False)
    events=[]
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            try:
                item=json.loads(line)
            except (TypeError,ValueError):
                continue
            unit = item.get("_SYSTEMD_UNIT") or item.get("UNIT") or ""
            if unit not in UNIT_NAMES:
                continue
            raw = item.get("MESSAGE") or ""
            if not isinstance(raw,str) or not ALLOWED.search(raw):
                continue
            micros = item.get("__REALTIME_TIMESTAMP")
            try:
                when=datetime.fromtimestamp(int(micros)/1_000_000,timezone.utc).isoformat()
            except (TypeError, ValueError, OverflowError):
                when=""
            events.append({"when":when,"unit":unit,
                           "level":str(item.get("PRIORITY","6"))[:2],
                           "message":scrub(raw)})
    payload={"snapshot_at": datetime.now(timezone.utc).isoformat(),
             "events":events[-100:],"journalctl_ok":result.returncode==0}
    DEST.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(DEST.parent,0,33) # Debian/Ubuntu www-data group GID 33
    os.chmod(DEST.parent,0o750)
    fd,path=tempfile.mkstemp(dir=DEST.parent,prefix=".snapshot.")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as out:
            json.dump(payload,out,ensure_ascii=False)
            out.flush();os.fsync(out.fileno())
        os.chown(path,0,33)
        os.chmod(path,0o640)
        os.replace(path,DEST)
    finally:
        if os.path.exists(path):
            os.unlink(path)

if __name__=="__main__":
    run()
