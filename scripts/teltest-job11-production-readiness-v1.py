#!/usr/bin/env python3
"""Read-only operator-safe Job 11 production go-live audit.

No network calls, no account identifiers, no message text, no mutations.
Summarizes recoverable failures, prior receipts, and all destination types.
"""
import collections
import json
import os
import pathlib
import re
import socket
import sqlite3
import subprocess
import sys

DB=pathlib.Path("/var/lib/teltest/data/teltest.sqlite3")
JOURNAL=pathlib.Path("/var/lib/teltest/eitaa-video-7084-private/one-send.json")

def active(unit):
    try:
        return subprocess.run(["systemctl","is-active","--quiet",unit],timeout=6).returncode==0
    except Exception:return False

def main():
    if os.geteuid()!=0 or socket.gethostname()!="VMID-20571":
        raise SystemExit("ERROR_WRONG_HOST_OR_USER")
    print("TELTEST_JOB11_PRODUCTION_READINESS_V1")
    print("TELTEST_ACTIVE="+str(active("teltest.service")))
    print("EITAA_GATEWAY_ACTIVE="+str(active("teltest-eitaa-gateway.service")))
    print("DELIVERY_TIMER_ACTIVE="+str(active("teltest-delivery.timer")))
    print("SCHEDULER_TIMER_ACTIVE="+str(active("teltest-scheduler.timer")))
    print("DELIVERY_WORKER_ACTIVE="+str(active("teltest-delivery.service")))
    print("GATEWAY_RUNTIME_PATCH20="+str(
      "// TELTEST_EITAA_VIDEO_7084_20_CHUNKS_V1" in pathlib.Path(
        "/var/lib/teltest-eitaa-gateway/runtime-v1/src/MainExpress.ts").read_text("utf8")))
    print("PRODUCTION_MODULE_PRESENT="+str(pathlib.Path(
        "/opt/teltest/repo/eitaa_authenticated_media.py").is_file()))
    run=subprocess.run(["systemctl","show","teltest-delivery.service",
                        "--property=TimeoutStartUSec,RuntimeMaxUSec",
                        "--no-pager"],capture_output=True,text=True,timeout=6)
    # only unit timing, no identifiers or secrets
    for ln in run.stdout.splitlines():
        if re.match(r"^(TimeoutStartUSec|RuntimeMaxUSec)=",ln):print("WORKER_"+ln)
    if JOURNAL.is_file() and not JOURNAL.is_symlink():
        try:
            state=json.loads(JOURNAL.read_text("utf8"))
            print("VIDEO_7084_MANUAL_ATTEMPT_STATUS="+str(state.get("status")))
            print("VIDEO_7084_MANUAL_ATTEMPT_HASH_MATCH="+str(state.get("sha256")==
              "0d60251e72eaf27641f677b58e4d5457eff9d2a28c31cd95a8f1b1cdb143273a"))
        except Exception:print("VIDEO_7084_ATTEMPT_JOURNAL_UNREADABLE")
    else:print("VIDEO_7084_ATTEMPT_JOURNAL_MISSING")
    if not DB.is_file() or DB.is_symlink():raise SystemExit("ERROR_DB_NOT_FOUND")
    db=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=10)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    print("SQLITE_QUICK_CHECK="+str(db.execute("PRAGMA quick_check").fetchone()[0]))
    q=db.execute("SELECT state,pause_requested,interval_seconds,max_attempts,due_at FROM delivery_queue WHERE job_id=11").fetchone()
    if not q:raise SystemExit("ERROR_JOB11_QUEUE_MISSING")
    print("JOB11_QUEUE_STATE="+str(q["state"]))
    print("JOB11_PAUSE_REQUESTED="+str(q["pause_requested"]))
    print("JOB11_INTERVAL_SECONDS="+str(q["interval_seconds"]))
    print("JOB11_MAX_ATTEMPTS="+str(q["max_attempts"]))
    print("ITEM_TOTAL="+str(db.execute("SELECT COUNT(*) FROM transfer_job_items WHERE transfer_job_id=11").fetchone()[0]))
    for row in db.execute("SELECT status,COUNT(*) AS count FROM transfer_job_items WHERE transfer_job_id=11 GROUP BY status ORDER BY status"):
        print("ITEM_STATUS_"+str(row["status"]).upper()+"="+str(row["count"]))
    for row in db.execute("""
       SELECT c.content_type AS kind,i.status AS status,COUNT(*) AS n
       FROM transfer_job_items i JOIN content_items c ON i.content_id=c.id
       WHERE i.transfer_job_id=11 GROUP BY c.content_type,i.status ORDER BY c.content_type,i.status
    """):
        print("CONTENT_GROUP="+str(row["kind"])+"/"+str(row["status"])+":"+str(row["n"]))
    for row in db.execute("SELECT provider_code,COUNT(*) n FROM transfer_destinations WHERE transfer_job_id=11 AND enabled=1 GROUP BY provider_code"):
        print("ACTIVE_DESTINATION_TYPE="+str(row["provider_code"])+":"+str(row["n"]))
    known=collections.Counter()
    for row in db.execute("""
      SELECT id,status,attempts,last_error FROM transfer_job_items WHERE transfer_job_id=11 AND status='failed'
    """):
        err=str(row["last_error"] or "").lower()
        if "nameerror" in err:category="NAMEERROR"
        elif "eitaa_media_not_binary" in err or "eitaa_media_html" in err or "eitaa_media_wrong_type" in err:category="PUBLIC_MEDIA_HTML_OR_WRONG_TYPE"
        elif "eitaa_auth_" in err:category="AUTH_MEDIA_FAILURE"
        elif "timeout" in err or "timed out" in err:category="TIMEOUT_UNCERTAIN"
        elif "eitaa" in err:category="OTHER_EITAA_ERROR"
        else:category="OTHER_UNCLASSIFIED"
        known[(category, "EXHAUSTED" if row["attempts"]>=q["max_attempts"] else "RETRY_LEFT")]+=1
    for (category,limit),count in sorted(known.items()):
        print("FAILED_CATEGORY="+category+"/"+limit+":"+str(count))
    receipts=collections.Counter()
    sql="""SELECT p.state AS state, COUNT(*) AS n
       FROM delivery_parts p JOIN transfer_job_items i ON i.id=p.item_id
       WHERE i.transfer_job_id=11 GROUP BY p.state"""
    for row in db.execute(sql):receipts[str(row["state"])]+=int(row["n"])
    for state,count in sorted(receipts.items()):
        print("DELIVERY_PART_STATE="+state+":"+str(count))
    affected=db.execute("""SELECT i.status,i.attempts,i.destination_external_id,
       (SELECT COUNT(*) FROM delivery_parts p WHERE p.item_id=i.id) AS parts
       FROM transfer_job_items i WHERE i.id=392801 AND i.transfer_job_id=11""").fetchone()
    if not affected:print("VIDEO_7084_ITEM_IN_JOB11=NO")
    else:
        print("VIDEO_7084_ITEM_IN_JOB11=YES")
        print("VIDEO_7084_ITEM_STATUS="+str(affected["status"]))
        print("VIDEO_7084_ITEM_PART_COUNT="+str(affected["parts"]))
        print("VIDEO_7084_ITEM_RECEIPT_PRESENT="+str(bool(affected["destination_external_id"])))
    for p in ("7069","7070","7072","7084"):
        records=db.execute("""
          SELECT i.status AS status,d.provider_code AS provider
          FROM transfer_job_items i
          JOIN content_items c ON c.id=i.content_id
          JOIN transfer_destinations d ON d.id=i.destination_id
          WHERE i.transfer_job_id=11 AND c.connector_code='eitaa'
            AND c.external_id=? AND d.enabled=1
        """,(p,)).fetchall()
        print("PREVIOUS_MANUAL_SUCCESS_"+p+"_MATCHES="+str(len(records)))
        for rec in records[:2]:
            print("PREVIOUS_MANUAL_SUCCESS_"+p+"_QUEUE_STATUS="+
                str(rec["provider"])+"/"+str(rec["status"]))
    print("JOB11_READ_ONLY_AUDIT_FINISHED_NO_MESSAGES_SENT")
    db.close()
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("AUDIT_ERROR_CLASS="+type(e).__name__)
        if isinstance(e,sqlite3.Error):print("DATABASE_LAYOUT_DIFFERENCE="+type(e).__name__)
        sys.exit(1)
