#!/usr/bin/env python3
"""Reconcile ONE interrupted Eitaa video send without upload, retry, or state mutation.

Read-only reconciliation of private at-most-once journal with most recent
authenticated Eitaa dialogs. A negative/inconclusive dialog check is NOT
proof of non-delivery: dialogs only shows recent messages.
Never prints message text, phone, names, tokens, access hashes, or raw media.
"""
from __future__ import annotations
import json, os, pathlib, socket, sqlite3, subprocess, sys
ROOT = pathlib.Path("/opt/teltest/repo")
DB = pathlib.Path("/var/lib/teltest/data/teltest.sqlite3")
JOURNAL = pathlib.Path("/var/lib/teltest/eitaa-video-7084-private/one-send.json")
EXPECTED_SIZE = 10095369
EXPECTED_SHA = "0d60251e72eaf27641f677b58e4d5457eff9d2a28c31cd95a8f1b1cdb143273a"
EXPECTED_ITEM = 392801
def good(cond,why):
    if not cond: raise RuntimeError(why)
def alive(unit):
    return subprocess.run(["systemctl","is-active","--quiet",unit],capture_output=True,timeout=6).returncode==0
def dbro():
    good(DB.is_file() and not DB.is_symlink(),"DATABASE_UNAVAILABLE")
    db=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=8)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db
def peer_of(m):
    for field in ("peer_id","to_id","peer","to"):
        val=m.get(field)
        if isinstance(val,dict):
            for label in ("channel_id","channelId"):
                if val.get(label) is not None:
                    return str(val[label])
    return ""
def visible_match(m,target,caption):
    if not isinstance(m,dict) or peer_of(m)!=str(target):return (False,False)
    media=m.get("media")
    if not isinstance(media,dict):return (False,True)
    doc=media.get("document")
    if not isinstance(doc,dict):return (False,True)
    try: size=int(doc.get("size") or 0)
    except (TypeError,ValueError):size=0
    text=m.get("message")
    if text is None:text=m.get("text")
    # A matching size AND exact caption provides a high-confidence
    # match only within the correct destination dialog.
    return (size==EXPECTED_SIZE and isinstance(text,str) and text==caption,True)
def main():
    good(socket.gethostname()=="VMID-20571" and os.geteuid()==0,"WRONG_HOST_OR_USER")
    print("TELTEST_INTERRUPTED_EITAA_VIDEO_SEND_RECONCILE_V1")
    print("ONE_VIDEO_EXPECTED_BYTES="+str(EXPECTED_SIZE))
    good(JOURNAL.is_file() and not JOURNAL.is_symlink(),"PRIVATE_ATTEMPT_JOURNAL_NOT_FOUND")
    data=json.loads(JOURNAL.read_text("utf8"))
    good(data.get("post")==7084 and data.get("transfer_item_id")==EXPECTED_ITEM,
         "JOURNAL_DOES_NOT_MATCH_POST_7084")
    good(data.get("sha256")==EXPECTED_SHA,"JOURNAL_FILE_HASH_MISMATCH")
    state=str(data.get("status") or "")
    good(state in {"sending_or_uncertain","confirmed_by_gateway"},"JOURNAL_STATUS_UNEXPECTED")
    print("PRIVATE_JOURNAL_STATUS="+state.upper())
    print("SOURCE_MP4_SHA256_MATCHES_PREVIOUS_DOWNLOAD=YES")
    print("GATEWAY_SERVICE_ACTIVE="+str(alive("teltest-eitaa-gateway.service")).upper())
    print("TELTEST_SERVICE_ACTIVE="+str(alive("teltest.service")).upper())
    timers=alive("teltest-delivery.timer") or alive("teltest-scheduler.timer")
    print("AUTO_TIMERS_INACTIVE="+str(not timers).upper())
    with dbro() as db:
        queue=db.execute("SELECT state,pause_requested FROM delivery_queue WHERE job_id=11").fetchone()
        good(queue is not None and tuple(queue)==("paused",1),"JOB11_STATE_CHANGED")
        rec=db.execute("""
           SELECT c.processed_text,c.raw_text,d.destination_ref
           FROM transfer_job_items i
           JOIN content_items c ON c.id=i.content_id
           JOIN transfer_destinations d ON d.id=i.destination_id
           WHERE i.id=? AND i.transfer_job_id=11 AND c.external_id='7084'
           AND d.enabled=1 LIMIT 1
        """,(EXPECTED_ITEM,)).fetchone()
        good(rec is not None,"EXPECTED_QUEUE_ITEM_NOT_FOUND")
        caption=str(rec["processed_text"] if rec["processed_text"] is not None
                    else (rec["raw_text"] or ""))[:4096]
    print("JOB11_PAUSED=YES")
    print("NO_MESSAGE_UPLOAD_OR_RETRY_WILL_BE_ATTEMPTED=YES")
    sys.path.insert(0,str(ROOT))
    from eitaa_live_gateway import get_target,gateway
    target=get_target(str(rec["destination_ref"]))
    good(target.get("status")=="connected","TARGET_ACCOUNT_NOT_CONNECTED")
    phone=target.get("phone")
    dest_peer=str(target.get("peer_id"))
    good(bool(phone) and dest_peer.isdecimal(),"INVALID_DESTINATION")
    try:
        gateway("auth/loadSession",{"phone":phone},timeout=8)
        result=gateway("messages/dialogs",{"phone":phone},timeout=12)
    except Exception as e:
        print("RECENT_DIALOG_INSPECTION="+type(e).__name__)
        print("DELIVERY_CONCLUSION=UNCERTAIN_DO_NOT_RESEND")
        return 0
    if not isinstance(result,dict) or not isinstance(result.get("messages"),list):
        print("RECENT_DIALOG_INSPECTION=UNEXPECTED_RESPONSE")
        print("DELIVERY_CONCLUSION=UNCERTAIN_DO_NOT_RESEND")
        return 0
    messages=result["messages"]
    same_dest=[m for m in messages if isinstance(m,dict) and peer_of(m)==dest_peer]
    matched=[m for m in same_dest if visible_match(m,dest_peer,caption)[0]]
    print("RECENT_DIALOG_MESSAGE_COUNT="+str(len(messages)))
    print("DESTINATION_DIALOG_MESSAGES_VISIBLE="+str(len(same_dest)))
    print("EXACT_VIDEO_SIZE_AND_CAPTION_MATCH="+("YES" if matched else "NOT_FOUND_IN_RECENT_DIALOGS"))
    if matched:
        print("DELIVERY_CONCLUSION=LIKELY_DELIVERED_VERIFY_IN_EITAA_APP")
    elif state=="confirmed_by_gateway":
        print("DELIVERY_CONCLUSION=GATEWAY_CONFIRMED_VERIFY_IN_EITAA_APP")
    else:
        print("DELIVERY_CONCLUSION=UNCERTAIN_DO_NOT_RESEND")
    print("READ_ONLY_END_NO_SECRETS_OR_TEXT_PRINTED")
    return 0
if __name__=="__main__":
    try:sys.exit(main())
    except Exception as exc:
        print("SAFE_STOP_CLASS="+type(exc).__name__)
        if isinstance(exc,RuntimeError):print("SAFE_STOP_REASON="+str(exc)[:90])
        print("NO_RETRY_DO_NOT_DELETE_ATTEMPT_JOURNAL")
        sys.exit(2)
