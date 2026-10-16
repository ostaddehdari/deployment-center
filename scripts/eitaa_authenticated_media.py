#!/usr/bin/env python3
"""Authenticated Eitaa media downloader for live TelTest delivery jobs.

Only source-channel messages already present in the selected job are accessed.
Uses an authenticated EitaaBun account joined to that channel. No send APIs.
"""
import asyncio
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

CHUNK = 524288
MAX_SIZE = 256 * 1024 * 1024
ACC_DB = Path("/var/lib/teltest/eitaa-accounts/live_accounts.sqlite3")


class EitaaMediaSourceError(RuntimeError):
    pass


def username(value):
    s = str(value or "").strip().lower()
    if s.startswith(("https://", "http://")):
        parsed = urlsplit(s)
        if parsed.scheme != "https" or parsed.hostname not in {"eitaa.com", "www.eitaa.com"}:
            return ""
        parts = [x for x in parsed.path.split("/") if x]
        if parts and parts[0] == "s":
            parts.pop(0)
        s = parts[0] if parts else ""
    if s.startswith("eitaa:"):
        s = s[6:]
    s = s.lstrip("@").split("/")[0]
    return s if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", s) else ""


def source_account(row):
    candidates = set(filter(None, (
        username(row.get("source_ref")), username(row.get("source_key"))
    )))
    if not candidates:
        raise EitaaMediaSourceError("EITAA_AUTH_SOURCE_USERNAME_MISSING")
    if not ACC_DB.is_file() or ACC_DB.is_symlink():
        raise EitaaMediaSourceError("EITAA_AUTH_ACCOUNTS_UNAVAILABLE")
    with sqlite3.connect("file:" + str(ACC_DB) + "?mode=ro", uri=True, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute("""
          SELECT DISTINCT ch.peer_id,a.phone
          FROM eitaa_live_channels ch
          JOIN eitaa_live_accounts a ON a.profile=ch.profile
          WHERE a.status='connected'
          AND LOWER(LTRIM(ch.username,'@')) IN
          (SELECT value FROM json_each(?))
        """, (json.dumps(sorted(candidates)),)).fetchall()
    if len(rows) != 1:
        raise EitaaMediaSourceError("EITAA_AUTH_SOURCE_ACCOUNT_NOT_UNIQUE")
    return rows[0]["phone"], int(rows[0]["peer_id"])


def descriptor(message):
    media = message.get("media") or {}
    doc = media.get("document") if isinstance(media, dict) else None
    if not isinstance(doc, dict):
        raise EitaaMediaSourceError("EITAA_AUTH_DOCUMENT_NOT_AVAILABLE")
    try:
        size = int(doc.get("size") or 0)
    except (TypeError, ValueError):
        raise EitaaMediaSourceError("EITAA_AUTH_INVALID_SIZE") from None
    if not 32 <= size <= MAX_SIZE:
        raise EitaaMediaSourceError("EITAA_AUTH_MEDIA_SIZE_OUT_OF_LIMIT")
    doc_id = str(doc.get("id") or "")
    access = str(doc.get("access_hash") or doc.get("accessHash") or "")
    if not re.fullmatch(r"-?[0-9]{1,25}", doc_id) or not re.fullmatch(r"-?[0-9]{1,25}", access):
        raise EitaaMediaSourceError("EITAA_AUTH_DOCUMENT_LOCATION_INVALID")
    ref = doc.get("file_reference")
    if ref is None:
        ref = doc.get("fileReference")
    if isinstance(ref, dict):
        try:
            ref = [ref[k] for k in sorted(ref, key=lambda k: int(k))]
        except (TypeError, ValueError):
            raise EitaaMediaSourceError("EITAA_AUTH_REFERENCE_INVALID") from None
    if not isinstance(ref, list) or not 1 <= len(ref) <= 512 or not all(
        type(n) is int and 0 <= n <= 255 for n in ref
    ):
        raise EitaaMediaSourceError("EITAA_AUTH_REFERENCE_INVALID")
    mime = str(doc.get("mime_type") or doc.get("mimeType") or "").lower()
    attributes = doc.get("attributes") or []
    video = mime.startswith("video/") or any(
        isinstance(v, dict) and "video" in str(v.get("_", "")).lower() for v in attributes
    )
    if video:
        extension = ".mp4" if mime != "video/webm" else ".webm"
    elif mime.startswith("audio/"):
        extension = ".ogg" if ("ogg" in mime or "opus" in mime) else ".mp3"
    else:
        extension = ".bin"
        for attr in attributes:
            if isinstance(attr, dict):
                n = str(attr.get("file_name") or "")
                suffix = Path(n).suffix.lower()
                if suffix in {".pdf", ".zip", ".rar", ".7z", ".doc", ".docx",
                              ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".apk",
                              ".mp3", ".ogg", ".mp4", ".webm"}:
                    extension = suffix
                    break
    return doc_id, access, ref, size, extension


def _download(source_row, directory, index):
    from eitaa_live_gateway import gateway
    post = str(source_row.get("external_id") or "")
    if not re.fullmatch(r"[0-9]{1,12}", post):
        raise EitaaMediaSourceError("EITAA_AUTH_SOURCE_POST_ID_INVALID")
    phone, peer_id = source_account(source_row)
    gateway("auth/loadSession", {"phone": phone}, timeout=25)
    result = gateway("messages/read", {
        "phone": phone, "id": peer_id, "type": "channel",
        "offset": int(post) + 1, "size": 2, "downward": False
    }, timeout=75)
    if not isinstance(result, dict) or not isinstance(result.get("messages"), list):
        raise EitaaMediaSourceError("EITAA_AUTH_HISTORY_UNEXPECTED")
    found = [m for m in result["messages"] if isinstance(m, dict) and str(m.get("id")) == post]
    if len(found) != 1:
        raise EitaaMediaSourceError("EITAA_AUTH_MESSAGE_NOT_FOUND")
    doc_id, access, ref, size, extension = descriptor(found[0])
    dest_dir = Path(directory)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / ("eitaa-auth-" + str(index) + extension)
    partial = dest_dir / ("eitaa-auth-" + str(index) + extension + ".partial")
    partial.unlink(missing_ok=True)
    target.unlink(missing_ok=True)
    written = 0
    try:
        with partial.open("xb") as out:
            for offset in range(0, size, CHUNK):
                result = gateway("messages/getFile", {
                    "phone": phone, "id": doc_id, "access_hash": access,
                    "file_reference": ref, "type": "document", "offset": offset
                }, timeout=120)
                values = result.get("data") if isinstance(result, dict) else None
                expected = min(CHUNK, size - offset)
                if not isinstance(values, list) or len(values) != expected or not all(
                    type(x) is int and 0 <= x <= 255 for x in values
                ):
                    raise EitaaMediaSourceError("EITAA_AUTH_CHUNK_INCOMPLETE")
                data = bytes(values)
                if offset == 0 and extension in (".mp4", ".webm"):
                    if not (data[4:8] == b"ftyp" or data.startswith(b"\x1a\x45\xdf\xa3")):
                        raise EitaaMediaSourceError("EITAA_AUTH_VIDEO_MAGIC_INVALID")
                out.write(data)
                written += len(data)
            out.flush()
            os.fsync(out.fileno())
        if written != size or partial.stat().st_size != size:
            raise EitaaMediaSourceError("EITAA_AUTH_FILE_SIZE_MISMATCH")
        os.replace(partial, target)
        return str(target)
    finally:
        partial.unlink(missing_ok=True)


async def download_eitaa_authenticated(url, directory, index, source_row, kind=None):
    """Only authenticated Eitaa video/audio/document; keep existing photo path."""
    if not isinstance(source_row, dict) or source_row.get("connector_code") != "eitaa":
        return None
    if str(kind or "").lower() not in {
        "video", "document", "file", "audio", "voice", "animation", "gif",
    }:
        return None
    parsed = urlsplit(str(url or ""))
    if parsed.scheme != "https" or parsed.hostname not in {"eitaa.com", "www.eitaa.com"}:
        return None
    return await asyncio.to_thread(_download, source_row, directory, index)
