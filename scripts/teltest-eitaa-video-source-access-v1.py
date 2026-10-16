#!/usr/bin/env python3
"""Read-only, redacted Eitaa video source-access inventory for TelTest.

No HTTP requests, login attempts, message contents, tokens or raw access hashes.
Does not create DB files and cannot start jobs.
"""
from __future__ import annotations
import argparse
import pathlib
import re
import socket
import sqlite3
import sys
from urllib.parse import urlparse

DB=pathlib.Path("/var/lib/teltest/data/teltest.sqlite3")
EITAA_DB=pathlib.Path("/var/lib/teltest/eitaa-accounts/live_accounts.sqlite3")
BRIDGE=pathlib.Path("/opt/teltest/repo/eitaa_live_gateway.py")
GATEWAY=pathlib.Path("/var/lib/teltest-eitaa-gateway/upstream/repo/src/MainExpress.ts")
PROVIDER=pathlib.Path("/opt/teltest/repo/provider_destinations.py")

def conn(path):
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError("MISSING_DATABASE_OR_UNEXPECTED_SYMLINK")
    c=sqlite3.connect("file:"+str(path)+"?mode=ro",uri=True,timeout=5)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA query_only=ON")
    return c

def columns(c,t):
    if not re.fullmatch(r"[a-z_]+",t):
        raise ValueError("BAD_TABLE_NAME")
    return {r["name"] for r in c.execute("PRAGMA table_info("+t+")")}

def userkey(raw):
    s=(raw or "").strip().lower()
    if not s:return ""
    if s.startswith("https://") or s.startswith("http://"):
        p=urlparse(s)
        if (p.hostname or "").lower() not in {"eitaa.com","www.eitaa.com"}:return ""
        parts=[v for v in p.path.split("/") if v]
        if parts and parts[0]=="s":parts=parts[1:]
        s=parts[0] if parts else ""
    s=s.lstrip("@")
    if "/" in s: s=s.split("/",1)[0]
    return s if re.fullmatch(r"[a-z][a-z0-9_]{2,63}",s) else ""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--post",default="7084")
    args=ap.parse_args()
    if not re.fullmatch(r"[0-9]{1,12}",args.post):
        raise SystemExit("ERROR_BAD_POST_NUMBER")
    if socket.gethostname()!="VMID-20571":
        raise SystemExit("ERROR_WRONG_HOST")
    print("TELTEST_EITAA_VIDEO_SOURCE_ACCESS_READ_ONLY_V1")
    for p in [DB,EITAA_DB]:
        if not p.is_file():
            print("MISSING_DB", "content" if p==DB else "eitaa_accounts")
            return 2
    with conn(DB) as c:
        cols=columns(c,"content_items")
        if not {"connector_code","external_id"}.issubset(cols):
            print("UNEXPECTED_CONTENT_SCHEMA")
            return 2
        fields=[k for k in ("source_ref","source_key") if k in cols]
        row=c.execute("SELECT "+(",".join(fields) if fields else "external_id")+
                      " FROM content_items WHERE connector_code='eitaa' AND external_id=? LIMIT 1",(args.post,)).fetchone()
        if not row:
            print("SOURCE_POST_IN_LIBRARY=NO")
            return 0
        print("SOURCE_POST_IN_LIBRARY=YES")
        keys=[userkey(str(row[k] or "")) for k in fields]
        keys=[k for k in keys if k]
        print("SOURCE_USERNAME_IDENTIFIER_AVAILABLE="+("YES" if keys else "NO"))
    with conn(EITAA_DB) as c:
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"eitaa_live_accounts","eitaa_live_channels"}.issubset(tables):
            print("UNEXPECTED_EITAA_ACCOUNT_SCHEMA")
            return 2
        accounts=c.execute("SELECT COUNT(*) FROM eitaa_live_accounts WHERE status='connected'").fetchone()[0]
        channels=c.execute("SELECT COUNT(*) FROM eitaa_live_channels").fetchone()[0]
        print("CONNECTED_EITAA_ACCOUNTS_COUNT=",accounts)
        print("SYNCED_EITAA_CHANNELS_COUNT=",channels)
        matched=0
        if keys:
            placeholders=",".join("?" for _ in keys)
            matched=c.execute("""
               SELECT COUNT(*)
               FROM eitaa_live_channels ch
               JOIN eitaa_live_accounts a ON a.profile=ch.profile
               WHERE a.status='connected'
                 AND LOWER(LTRIM(ch.username,'@')) IN ("""+placeholders+")",keys).fetchone()[0]
        print("SOURCE_CHANNEL_IN_SYNCED_CONNECTED_ACCOUNTS="+("YES" if matched else "NOT_CONFIRMED"))
        if not matched:
            print("NEXT_ACTION=VERIFY_SOURCE_CHANNEL_ACCESS_BEFORE_ATTEMPTING_VIDEO_GETFILE")
    if BRIDGE.is_file():
        b=BRIDGE.read_text(encoding="utf8")
        print("TELTEST_READ_ROUTE_ALLOWED="+("YES" if '"messages/read"' in b or "'messages/read'" in b else "NO"))
        print("TELTEST_GETFILE_ROUTE_ALLOWED="+("YES" if '"messages/getFile"' in b or "'messages/getFile'" in b else "NO"))
    else: print("TELTEST_BRIDGE_MISSING")
    if GATEWAY.is_file():
        g=GATEWAY.read_text(encoding="utf8")
        print("GATEWAY_READ_ROUTE_ALLOWED="+("YES" if "'POST /eitaa/messages/read'" in g else "NO"))
        print("GATEWAY_GETFILE_ROUTE_ALLOWED="+("YES" if "'POST /eitaa/messages/getFile'" in g else "NO"))
    else:print("UPSTREAM_GATEWAY_SOURCE_MISSING")
    if PROVIDER.is_file():
        print("PROVIDER_CODE_PRESENT=YES")
    print("READ_ONLY_END_NO_MESSAGES_OR_SECRETS_PRINTED")
    return 0

if __name__=="__main__":
    try: sys.exit(main())
    except (sqlite3.Error, OSError, ValueError) as exc:
        print("DIAGNOSTIC_FAILURE="+type(exc).__name__)
        sys.exit(2)
