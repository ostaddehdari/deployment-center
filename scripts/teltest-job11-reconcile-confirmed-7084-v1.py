#!/usr/bin/env python3
"""Reconcile user-confirmed Eitaa video 7084 into paused Job 11 safely.

--check prints only redacted state. --apply takes a private online SQLite backup
and marks exactly one previously failed Job-11 transfer item transferred.
No network calls, sending, queue enable, timer or service modification.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

DB=Path("/var/lib/teltest/data/teltest.sqlite3")
JOURNAL=Path("/var/lib/teltest/eitaa-video-7084-private/one-send.json")
BACKUP=Path("/opt/teltest/backups/eitaa-video-7084-manual-reconciliation")
ITEM=392801
CONTENT=216551
FULL_SHA="0d60251e72eaf27641f677b58e4d5457eff9d2a28c31cd95a8f1b1cdb143273a"

def must(test, reason):
    if not test:raise RuntimeError(reason)

def active(name):
    return subprocess.run(["systemctl","is-active","--quiet",name],
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                          timeout=8).returncode==0

def connect(readonly=False):
    uri="file:"+str(DB)+"?mode="+("ro" if readonly else "rw")
    db=sqlite3.connect(uri,uri=True,timeout=30,isolation_level=None)
    db.row_factory=sqlite3.Row
    if readonly:db.execute("PRAGMA query_only=ON")
    return db

def verify(db):
    must(socket.gethostname()=="VMID-20571" and os.geteuid()==0,"WRONG_HOST_OR_USER")
    for svc in ("teltest.service","teltest-eitaa-gateway.service"):
        must(active(svc),"SERVICE_NOT_ACTIVE")
    for svc in ("teltest-delivery.timer","teltest-scheduler.timer","teltest-delivery.service"):
        must(not active(svc),"DELIVERY_TIMER_OR_WORKER_ACTIVE")
    must(DB.is_file() and not DB.is_symlink(),"DB_UNAVAILABLE")
    must(JOURNAL.is_file() and not JOURNAL.is_symlink(),"PRIVATE_SEND_JOURNAL_UNAVAILABLE")
    info=json.loads(JOURNAL.read_text(encoding="utf8"))
    must(info.get("post")==7084 and info.get("content_id")==CONTENT and
         info.get("transfer_item_id")==ITEM and info.get("job")==11,
         "SEND_JOURNAL_ID_MISMATCH")
    must(info.get("sha256")==FULL_SHA,"MP4_SHA256_FROM_PRIOR_SUCCESS_MISMATCH")
    must(info.get("status") in ("sending_or_uncertain","confirmed_by_gateway"),
         "JOURNAL_UNEXPECTED_STATUS")
    q=db.execute("SELECT state,pause_requested FROM delivery_queue WHERE job_id=11").fetchone()
    must(q is not None and (q["state"],q["pause_requested"])==("paused",1),
         "JOB11_NOT_PAUSED")
    rows=db.execute("""
      SELECT i.id,i.status,i.content_id,i.attempts,i.destination_external_id,
             c.external_id,c.connector_code,d.provider_code,d.enabled,
             (SELECT COUNT(*) FROM delivery_parts p WHERE p.item_id=i.id) AS part_count
      FROM transfer_job_items i
      JOIN content_items c ON c.id=i.content_id
      JOIN transfer_destinations d ON d.id=i.destination_id
      WHERE i.id=? AND i.transfer_job_id=11
    """,(ITEM,)).fetchall()
    must(len(rows)==1,"TRANSFER_ITEM_LOOKUP_AMBIGUOUS")
    row=rows[0]
    must(row["content_id"]==CONTENT and row["external_id"]=="7084"
         and row["connector_code"]=="eitaa" and row["provider_code"]=="eitaa_user"
         and row["enabled"]==1,"TRANSFER_ITEM_SOURCE_DESTINATION_CHANGED")
    must(row["part_count"]==0,"DELIVERY_PARTS_REQUIRE_SEPARATE_RECONCILIATION")
    if row["status"]=="transferred":
        return "already_transferred"
    must(row["status"]=="failed","TRANSFER_ITEM_HAS_UNSAFE_STATUS")
    must(row["destination_external_id"] is None or not str(row["destination_external_id"]).strip(),
         "TARGET_RECEIPT_PRESENT_REQUIRE_MANUAL_REVIEW")
    return "ready"

def main():
    parser=argparse.ArgumentParser()
    x=parser.add_mutually_exclusive_group(required=True)
    x.add_argument("--check",action="store_true")
    x.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    db=connect(readonly=args.check)
    try:
        if args.apply:db.execute("BEGIN IMMEDIATE")
        status=verify(db)
        print("TELTEST_JOB11_VIDEO_7084_RECONCILE_V1")
        print("POST_7084_ORIGINAL_CONTENT_ID=216551")
        print("POST_7084_TRANSFER_ITEM_ID=392801")
        print("FULL_MP4_PRIOR_SHA256_MATCH=YES")
        print("DESTINATION_PROVIDER=eitaa_user")
        print("JOB11_PAUSED_AND_TIMERS_INACTIVE=YES")
        print("CURRENT_RECONCILIATION_STATE="+status.upper())
        if args.check:
            print("READ_ONLY_CHECK_OK_NO_MUTATIONS")
            return
        if status=="already_transferred":
            db.commit()
            print("ALREADY_RECONCILED_NO_CHANGES")
            return
        BACKUP.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(BACKUP,0o700)
        name=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target=BACKUP/("before-7084-"+name+".sqlite3")
        must(not target.exists(),"BACKUP_NAME_COLLISION")
        # sqlite3.online backup, retains WAL-consistent snapshot.
        # End the write-intent transaction before backing up to prevent lock
        # starvation; then re-check after acquiring the write lock.
        db.rollback()
        with sqlite3.connect(str(target),timeout=30) as dst:
            src=connect(readonly=True)
            try:src.backup(dst,pages=128,sleep=0.05)
            finally:src.close()
        os.chmod(target,0o600)
        db.execute("BEGIN IMMEDIATE")
        must(verify(db)=="ready","JOB11_STATE_CHANGED_DURING_BACKUP")
        changed=db.execute("""
          UPDATE transfer_job_items SET
            status='transferred',last_error=NULL,
            transferred_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP
          WHERE id=? AND content_id=? AND transfer_job_id=11 AND status='failed'
        """,(ITEM,CONTENT)).rowcount
        must(changed==1,"EXPECTED_ONE_ROW_UPDATE")
        db.commit()
        print("RECONCILED_ONE_CONFIRMED_VIDEO=YES")
        print("PROTECTED_DB_BACKUP="+str(target))
        print("JOB11_STILL_PAUSED=YES")
        print("NO_POSTS_SENT=YES")
    finally:
        if db.in_transaction:db.rollback()
        db.close()

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("RECONCILIATION_SAFE_STOP="+type(e).__name__)
        if isinstance(e,RuntimeError):print("DETAIL="+str(e)[:110])
        sys.exit(1)
