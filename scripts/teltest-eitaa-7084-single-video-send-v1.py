#!/usr/bin/env python3
"""One Eitaa-to-Eitaa MP4 post test: post 7084 to Job-11's single verified Eitaa target.

Downloads verified 20 chunks, then makes AT MOST ONE media send attempt.
Does not touch delivery queues or enable timers. Its private journal prevents
automatic re-send when the upstream response is ambiguous.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

POST = "7084"
TRANSFER_ITEM_ID = 392801
EXPECTED_SIZE = 10095369
EXPECTED_FIRST_SHA256 = "533f14d957e8ffa73b7313656bbe7673f7db1124a91281ffcb2b4a316590f0bb"
CHUNK = 524288
CHUNKS = 20
DB = Path("/var/lib/teltest/data/teltest.sqlite3")
ACC = Path("/var/lib/teltest/eitaa-accounts/live_accounts.sqlite3")
LOCK = Path("/var/lib/teltest/eitaa-video-7084-private/lock")
JOURNAL = Path("/var/lib/teltest/eitaa-video-7084-private/one-send.json")
APP = Path("/opt/teltest/repo")

def fail(msg):
    raise RuntimeError(msg)

def needed(condition,reason):
    if not condition:
        fail(reason)

def connected(path):
    needed(path.is_file() and not path.is_symlink(), "DATABASE_UNAVAILABLE")
    c = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA query_only=ON")
    return c

def active(unit):
    return subprocess.run(["systemctl","is-active","--quiet",unit],
            capture_output=True, timeout=8).returncode == 0

def channel_username(raw):
    value = str(raw or "").strip()
    if value.startswith("https://"):
        u = urlsplit(value)
        if u.hostname not in ("eitaa.com","www.eitaa.com") or u.username or u.password:
            return ""
        parts = [x for x in u.path.split("/") if x]
        if parts and parts[0] == "s":
            parts = parts[1:]
        value = parts[0] if parts else ""
    value = value.lstrip("@").split("/")[0].lower()
    return value if re.fullmatch(r"[a-z][a-z0-9_]{2,63}",value) else ""

def guard():
    needed(socket.gethostname() == "VMID-20571" and os.geteuid() != 0,
           "WRONG_HOST_OR_MUST_RUN_AS_WEB_USER")
    for s in ("teltest.service","teltest-eitaa-gateway.service"):
        needed(active(s), "REQUIRED_SERVICE_INACTIVE")
    for s in ("teltest-delivery.timer","teltest-scheduler.timer","teltest-delivery.service"):
        needed(not active(s), "AUTO_DELIVERY_MUST_BE_OFF")
    needed(not JOURNAL.exists(), "VIDEO_POST_7084_ALREADY_ATTEMPTED_CHECK_JOURNAL")
    with connected(DB) as c:
        needed(c.execute("SELECT state,pause_requested FROM delivery_queue WHERE job_id=11").fetchone()[:]
               == ("paused",1), "JOB11_NOT_PAUSED")
        needed(c.execute("SELECT COUNT(*) FROM delivery_queue WHERE state='running'").fetchone()[0] == 0,
               "OTHER_DELIVERY_IS_RUNNING")
        needed(c.execute("""SELECT COUNT(*) FROM transfer_job_items
            WHERE transfer_job_id=11 AND status IN ('transferring','uncertain')""").fetchone()[0] == 0,
               "JOB11_HAS_UNCERTAIN_ITEM")

def sources_and_destination():
    with connected(DB) as db:
        # TRANSFER_ITEM_ID is an item in the delivery queue, NOT a content_items.id.
        # Resolve the original content row through its foreign key.
        content = db.execute("""SELECT c.id,c.external_id,c.source_ref,c.source_key,
                    c.processed_text,c.raw_text,c.connector_code
                    FROM transfer_job_items i JOIN content_items c ON c.id=i.content_id
                    WHERE i.id=? AND i.transfer_job_id=11
                      AND c.external_id=? AND c.connector_code='eitaa'""",
                    (TRANSFER_ITEM_ID,POST)).fetchone()
        needed(content is not None, "EXPECTED_VIDEO_POST_NOT_FOUND")
        destinations = db.execute("""SELECT destination_ref,provider_code
               FROM transfer_destinations WHERE transfer_job_id=11 AND enabled=1""").fetchall()
        needed(len(destinations)==1 and destinations[0]["provider_code"]=="eitaa_user",
               "JOB11_TARGET_NOT_A_SINGLE_USER_EITAA_CHANNEL")
        entries = db.execute("""SELECT i.status FROM transfer_job_items i
              JOIN content_items c ON c.id=i.content_id
              JOIN transfer_destinations d ON d.id=i.destination_id
              WHERE i.transfer_job_id=11 AND c.id=? AND d.enabled=1""",
              (int(content["id"]),)).fetchall()
        needed(len(entries)==1, "VIDEO_ITEM_NOT_UNIQUE_IN_JOB11")
        needed(entries[0]["status"] not in ("transferred","sent","delivered","done","success","completed","uncertain"),
               "VIDEO_ITEM_ALREADY_SENT_IN_JOB11")
        keys = sorted(set(filter(None,
                  (channel_username(content["source_ref"]),channel_username(content["source_key"])))))
        needed(bool(keys),"SOURCE_CHANNEL_USERNAME_NOT_AVAILABLE")
        caption = str(content["processed_text"] if content["processed_text"] is not None
                      else (content["raw_text"] or ""))[:4096]
        return int(content["id"]), keys, str(destinations[0]["destination_ref"]),caption

def media_descriptor(msg):
    doc = (msg.get("media") or {}).get("document")
    needed(isinstance(doc,dict),"EXPECTED_VIDEO_DOCUMENT_MISSING")
    mime = str(doc.get("mime_type") or doc.get("mimeType") or "").lower()
    attributes = doc.get("attributes") or []
    video = mime.startswith("video/") or any(
       isinstance(a,dict) and "video" in str(a.get("_") or "").lower()
       for a in attributes)
    needed(video,"DOCUMENT_NOT_A_VIDEO")
    size = int(doc.get("size") or 0)
    needed(size==EXPECTED_SIZE,"VIDEO_SIZE_CHANGED_FROM_VERIFIED_PROBE")
    did = str(doc.get("id") or "")
    access = str(doc.get("access_hash") or doc.get("accessHash") or "")
    needed(bool(re.fullmatch(r"-?[0-9]{1,25}",did)) and
           bool(re.fullmatch(r"-?[0-9]{1,25}",access)), "INVALID_MEDIA_LOCATION")
    ref = doc.get("file_reference")
    if ref is None:
        ref = doc.get("fileReference")
    if isinstance(ref,dict):
        try:
            vals=[ref[k] for k in sorted(ref,key=lambda k:int(k))]
        except (TypeError,ValueError):
            fail("MEDIA_REFERENCE_UNEXPECTED")
    elif isinstance(ref,list):
        vals=ref
    else:
        fail("MEDIA_REFERENCE_MISSING")
    needed(len(vals)==29 and all(type(x) is int and 0<=x<=255 for x in vals),
           "MEDIA_REFERENCE_CHANGED_OR_INVALID")
    return did,access,vals,size

def journal_write(status, content_id, full_sha=None):
    data={"post":7084,"content_id":content_id,"transfer_item_id":TRANSFER_ITEM_ID,"job":11,"status":status}
    if full_sha:
        data["sha256"]=full_sha
    tmp=JOURNAL.with_suffix(".json.tmp")
    fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,"w") as f:
            json.dump(data,f,sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,JOURNAL)
    finally:
        if tmp.exists():
            tmp.unlink()

def main():
    argp=argparse.ArgumentParser()
    argp.add_argument("--preflight",action="store_true",
                      help="validate target, state, permissions; no download or send")
    args=argp.parse_args()
    guard()
    needed(JOURNAL.parent.is_dir() and not JOURNAL.parent.is_symlink() and
           os.access(JOURNAL.parent,os.W_OK),"PRIVATE_JOURNAL_FOLDER_NOT_READY")
    needed(LOCK.is_file() and not LOCK.is_symlink(),"WORKER_LOCK_MISSING")
    with LOCK.open("a") as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        guard()
        content_id, keys, dest_ref, caption = sources_and_destination()
        sys.path.insert(0,str(APP))
        from eitaa_live_gateway import gateway,get_target
        from eitaa_media_exchange import readable_gateway_copy
        dest=get_target(dest_ref)
        needed(dest["can_post"]==1 and dest["status"]=="connected",
               "DESTINATION_NOT_POSTABLE")
        with connected(ACC) as c:
            matches=c.execute("""SELECT ch.peer_id,a.phone FROM eitaa_live_channels ch
                 JOIN eitaa_live_accounts a ON ch.profile=a.profile
                 WHERE a.status='connected' AND LOWER(LTRIM(ch.username,'@')) IN
                 (SELECT value FROM json_each(?))""",(json.dumps(keys),)).fetchall()
        needed(len(matches)==1,"SOURCE_ACCOUNT_AMBIGUOUS")
        source=matches[0]
        needed(source["phone"]==dest["phone"],"CROSS_ACCOUNT_UNSUPPORTED")
        needed(str(source["peer_id"])!=str(dest["peer_id"]),"SOURCE_AND_DESTINATION_ARE_IDENTICAL")
        print("EITAA_7084_SINGLE_VIDEO_POST_TEST")
        print("TARGET=JOB11_SINGLE_VERIFIED_EITAA_CHANNEL")
        print("DESTINATION_VERIFIED_AND_DIFFERENT_FROM_SOURCE=YES")
        print("CAPTION_LENGTH="+str(len(caption)))
        print("CONTENT_ID_RESOLVED_VIA_ITEM_FK="+str(content_id))
        print("JOB11_TIMERS_PAUSED_NO_DB_MUTATIONS=YES")
        from eitaa_media_exchange import SPOOL
        needed(SPOOL.is_dir() and not SPOOL.is_symlink(),"MEDIA_EXCHANGE_SPOOL_NOT_AVAILABLE")
        if args.preflight:
            print("PRECHECK_OK_ONE_VIDEO_7084_READY_NO_NETWORK_CALLS_NO_SEND")
            return

        gateway("auth/loadSession",{"phone":source["phone"]},timeout=25)
        data=gateway("messages/read",{"phone":source["phone"],"id":int(source["peer_id"]),
                 "type":"channel","offset":7085,"size":3,"downward":False},timeout=60)
        needed(isinstance(data,dict) and isinstance(data.get("messages"),list),
               "VIDEO_MESSAGE_HISTORY_UNEXPECTED")
        selection=[v for v in data["messages"] if isinstance(v,dict) and v.get("id")==7084]
        needed(len(selection)==1,"POST_7084_NOT_FOUND")
        document_id,hash_value,reference,size=media_descriptor(selection[0])
        print("VIDEO_METADATA_OK=YES")
        print("EXPECTED_CHUNKS=20")
        with tempfile.TemporaryDirectory(prefix="teltest-7084-single-video-") as folder:
            file=Path(folder)/"post-7084.mp4"
            total=0
            full=hashlib.sha256()
            with file.open("xb") as out:
                for index in range(CHUNKS):
                    off=index*CHUNK
                    result=gateway("messages/getFile",{
                        "phone":source["phone"],"id":document_id,
                        "access_hash":hash_value,"file_reference":reference,
                        "type":"document","offset":off},timeout=100)
                    values=result.get("data") if isinstance(result,dict) else None
                    length=min(CHUNK,size-off)
                    needed(isinstance(values,list) and len(values)==length and
                           all(type(v) is int and 0<=v<=255 for v in values),
                           "CHUNK_LENGTH_OR_VALUES_INVALID_"+str(index))
                    block=bytes(values)
                    if index==0:
                        needed(block[4:8]==b"ftyp","MP4_MAGIC_INVALID")
                        needed(hashlib.sha256(block).hexdigest()==EXPECTED_FIRST_SHA256,
                               "FIRST_CHUNK_DIFFERS_FROM_VERIFIED_PROBE")
                    out.write(block)
                    full.update(block)
                    total+=len(block)
                    print("CHUNK_"+str(index+1).zfill(2)+"_OF_20_OK="+str(len(block)),flush=True)
                out.flush()
                os.fsync(out.fileno())
            needed(total==size and file.stat().st_size==size,"DOWNLOADED_FILE_SIZE_INCORRECT")
            digest=full.hexdigest()
            print("COMPLETE_MP4_BYTES="+str(size),flush=True)
            print("COMPLETE_MP4_SHA256="+digest,flush=True)
            print("DOWNLOAD_FULL_SIZE_VERIFIED=YES",flush=True)
            # The private journal is created only immediately before sending.
            # Any ambiguous upstream response leaves a fail-closed uncertain entry.
            guard()
            payload={"phone":dest["phone"],"id":int(dest["peer_id"]),
                     "access_hash":int(dest["access_hash"]),
                     "type":"channel","message":caption,
                     "media_type":"file"}
            with readable_gateway_copy(file) as spool_path:
                payload["path"]=spool_path
                journal_write("sending_or_uncertain",content_id,digest)
                print("SINGLE_MEDIA_SEND_ATTEMPT_STARTED=YES",flush=True)
                response=gateway("messages/sendMedia",payload,timeout=900)
                needed(isinstance(response,dict) and response.get("result")=="ok",
                       "UPLOAD_RESULT_UNCONFIRMED_NO_AUTOMATIC_RETRY")
                journal_write("confirmed_by_gateway",content_id,digest)
                print("VIDEO_SEND_RESULT_OK=YES",flush=True)
                print("TARGET=JOB11_SINGLE_EITAA_CHANNEL",flush=True)
                print("UPLOAD_MEDIA_TYPE=FILE_MAY_DISPLAY_AS_ATTACHMENT",flush=True)
                print("JOB11_TIMERS_UNCHANGED=YES",flush=True)
                print("NO_AUTOMATIC_RETRY=YES",flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("VIDEO_TEST_STOP_CLASS="+type(e).__name__,flush=True)
        if isinstance(e,RuntimeError):
            print("VIDEO_TEST_STOP_REASON="+str(e)[:100],flush=True)
        print("NEVER_REPEAT_SEND_WITHOUT_CHECKING_DESTINATION",flush=True)
        sys.exit(1)
