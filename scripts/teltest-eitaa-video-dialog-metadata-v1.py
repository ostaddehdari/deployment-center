#!/usr/bin/env python3
"""TelTest Eitaa video metadata audit using ALREADY-ALLOWED dialogs route only.

This script never sends OTP, files or messages, opens no public ports and does
not print private account, access-hash, media reference, text or session data.
"""
from __future__ import annotations
import json
import pathlib
import re
import socket
import sqlite3
import sys
from urllib.parse import urlparse

if socket.gethostname() != "VMID-20571":
    raise SystemExit("ERROR_WRONG_HOST")
DB = pathlib.Path("/var/lib/teltest/data/teltest.sqlite3")
ACCOUNTS = pathlib.Path("/var/lib/teltest/eitaa-accounts/live_accounts.sqlite3")
SOURCE = pathlib.Path("/opt/teltest/repo")
sys.path.insert(0, str(SOURCE))
print("VIDEO_DIALOG_METADATA_AUDIT_V1")
def conn(path):
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("REQUIRED_DB_MISSING_OR_SYMLINK")
    db = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db

def key(value):
    val = str(value or "").strip()
    if val.startswith("http"):
        parsed = urlparse(val)
        if parsed.scheme != "https" or parsed.hostname not in ("eitaa.com", "www.eitaa.com"):
            return ""
        val = parsed.path.strip("/")
        if val.startswith("s/"): val = val[2:]
        val = val.split("/")[0]
    val = val.lstrip("@").split("/")[0].lower()
    return val if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", val) else ""

def chanid(obj):
    if not isinstance(obj, dict):
        return ""
    for k in ("channel_id","channelId"):
        if obj.get(k) is not None:
            return str(obj[k])
    for field in ("peer_id","peer","to_id","to","channel"):
        if isinstance(obj.get(field), dict):
            result = chanid(obj[field])
            if result: return result
    return ""

def media_kind(msg):
    media = msg.get("media") if isinstance(msg, dict) else None
    if not isinstance(media, dict):
        return "none", False, False, False, False
    doc = media.get("document")
    if not isinstance(doc, dict): doc = {}
    mime = str(doc.get("mime_type") or doc.get("mimeType") or "")[:80].lower()
    kind = str(media.get("_") or "unknown")[:64]
    return kind, bool(doc.get("id")), bool(doc.get("file_reference") or doc.get("fileReference")), mime.startswith("video/"), bool(doc.get("size"))

try:
    with conn(DB) as db:
        row = db.execute("""
            SELECT source_ref, source_key FROM content_items
            WHERE connector_code='eitaa' AND external_id='7084'
            LIMIT 1
        """).fetchone()
        if not row: raise RuntimeError("VIDEO_POST_7084_NOT_FOUND")
        keys = set(filter(None, (key(row["source_ref"]), key(row["source_key"]))))
        if not keys: raise RuntimeError("SOURCE_USERNAME_UNAVAILABLE")
    with conn(ACCOUNTS) as db:
        matches = [r for r in db.execute("""
            SELECT c.profile,c.peer_id,a.phone FROM eitaa_live_channels c
            JOIN eitaa_live_accounts a ON a.profile=c.profile
            WHERE a.status='connected' AND LOWER(LTRIM(c.username,'@')) IN (
                SELECT value FROM json_each(?)
            )
        """, (json.dumps(sorted(keys)),))]
    print("SOURCE_CHANNEL_ACCESSIBLE="+("YES" if matches else "NO"))
    print("SOURCE_ACCOUNT_MATCH_COUNT="+str(len(matches)))
    if len(matches) != 1:
        print("SAFE_STOP_EXPECT_EXACTLY_ONE_SOURCE_ACCOUNT")
        raise SystemExit(0)
    acct = matches[0]

    # Import the production client; do not call the send or login endpoints.
    from eitaa_live_gateway import gateway
    gateway("auth/loadSession", {"phone": acct["phone"]}, timeout=20)
    result = gateway("messages/dialogs", {"phone": acct["phone"]}, timeout=40)
    print("DIALOG_REQUEST=OK")
    if not isinstance(result,dict): raise RuntimeError("DIALOG_RESPONSE_NOT_OBJECT")
    messages = result.get("messages")
    if not isinstance(messages,list): raise RuntimeError("DIALOG_MESSAGES_NOT_LIST")
    chats = result.get("chats")
    print("DIALOG_MESSAGE_COUNT="+str(len(messages)))
    print("DIALOG_CHAT_COUNT="+str(len(chats) if isinstance(chats,list) else 0))
    target = [m for m in messages if isinstance(m,dict) and chanid(m) == str(acct["peer_id"])]
    print("SOURCE_CHANNEL_DIALOG_MESSAGES="+str(len(target)))
    for msg in target[:4]:
        msg_id = msg.get("id")
        if not isinstance(msg_id,int): continue
        kind,doc,ref,video,size = media_kind(msg)
        print("POST_ID="+str(msg_id)+" MEDIA_TYPE="+kind+
              " DOCUMENT_ID_PRESENT="+str(doc)+
              " FILE_REFERENCE_PRESENT="+str(ref)+
              " VIDEO_MIME="+str(video)+" SIZE_PRESENT="+str(size))
    if not any(isinstance(m.get("id"),int) and m["id"] == 7084 for m in target):
        print("POST_7084_IN_DIALOG_SUMMARY=NO")
        print("NEXT=PINNED_METADATA_READ_ROUTE_NEEDED")
    else:
        print("POST_7084_IN_DIALOG_SUMMARY=YES")
        print("NEXT=REVIEW_REDACTED_VIDEO_MEDIA_SCHEMA")
    print("AUDIT_FINISHED_NO_MEDIA_DOWNLOADED_NO_MESSAGES_SENT")
except (sqlite3.Error, OSError, ValueError, RuntimeError) as exc:
    print("AUDIT_ERROR_CLASS="+type(exc).__name__)
    print("NO_SECRETS_PRINTED")
    sys.exit(2)
