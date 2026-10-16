#!/usr/bin/env python3
"""Read-only preflight for a pinned, least-privilege Eitaa history route.
Checks the RUNNING gateway checkout, not the upstream source checkout.
No database changes, service restarts, network calls or message sending.
"""
import ast, hashlib, os, pathlib, socket, sqlite3, subprocess, sys
P = pathlib.Path("/opt/teltest/repo/eitaa_live_gateway.py")
G = pathlib.Path("/var/lib/teltest-eitaa-gateway/runtime-v1/src/MainExpress.ts")
def check(cond, msg):
    if not cond: raise RuntimeError(msg)
def active(name):
    return subprocess.run(["systemctl","is-active","--quiet",name]).returncode == 0
def digest(s):
    return hashlib.sha256(s.encode("utf8")).hexdigest()[:16]
try:
    check(socket.gethostname()=="VMID-20571" and os.geteuid()==0,"WRONG_SERVER_OR_USER")
    check(P.is_file() and not P.is_symlink(),"CLIENT_NOT_FOUND")
    check(G.is_file() and not G.is_symlink(),"RUNNING_GATEWAY_SOURCE_NOT_FOUND")
    check(active("teltest.service") and active("teltest-eitaa-gateway.service"),"SERVICE_INACTIVE")
    check(not active("teltest-delivery.timer") and not active("teltest-scheduler.timer"),"TIMERS_MUST_REMAIN_OFF")
    with sqlite3.connect("file:/var/lib/teltest/data/teltest.sqlite3?mode=ro",uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        check(db.execute("SELECT state,pause_requested FROM delivery_queue WHERE job_id=11").fetchone()==("paused",1),"JOB11_NOT_PAUSED")
        check(db.execute("SELECT COUNT(*) FROM delivery_queue WHERE state='running'").fetchone()[0]==0,"ACTIVE_QUEUE")
    py=P.read_text("utf8")
    js=G.read_text("utf8")
    check("# TELTEST_EITAA_SECURED_CLIENT_V1" in py,"CLIENT_AUTH_MISSING")
    check("// TELTEST_EITAA_GATEWAY_ACCESS_CONTROL_V1" in js,"GATEWAY_AUTH_MISSING")
    check("app.listen(port, '127.0.0.1'" in js,"GATEWAY_NOT_LOOPBACK")
    check("const allowedRoutes = new Set([" in js and "timingSafeEqual" in js,"GATEWAY_TOKEN_ALLOWLIST_MISSING")
    anchor_js="            'POST /eitaa/messages/dialogs',"
    anchor_py='"messages/dialogs", "messages/send", "messages/sendMedia"'
    print("VIDEO_HISTORY_ROUTE_PREFLIGHT_V2")
    print("RUNNING_GATEWAY_PATH="+str(G))
    print("TELTEST_CLIENT_PATH="+str(P))
    print("GATEWAY_AUTH_AND_LOOPBACK=YES")
    print("JOB11_PAUSED_TIMERS_OFF=YES")
    print("RUNTIME_READ_ROUTE_PRESENT="+("YES" if "'POST /eitaa/messages/read'" in js else "NO"))
    print("CLIENT_READ_ROUTE_PRESENT="+("YES" if '"messages/read"' in py else "NO"))
    print("GATEWAY_GETFILE_ROUTE_PRESENT="+("YES" if "'POST /eitaa/messages/getFile'" in js else "NO"))
    print("CLIENT_GETFILE_ROUTE_PRESENT="+("YES" if '"messages/getFile"' in py else "NO"))
    check(js.count(anchor_js)==1 and py.count(anchor_py)==1,"EXPECTED_ALLOWLIST_ANCHORS_MISSING_OR_CHANGED")
    newjs=js.replace(anchor_js,anchor_js+"\n            // TELTEST_EITAA_VIDEO_READ_ROUTE_V1\n            'POST /eitaa/messages/read',",1)
    newpy=py.replace(anchor_py,'"messages/dialogs", "messages/read", "messages/send", "messages/sendMedia"',1)
    ast.parse(newpy)
    print("READ_ONLY_PATCH_FEASIBLE=YES")
    print("PREPARED_RUNTIME_JS_SHA256_PREFIX="+digest(newjs))
    print("PREPARED_CLIENT_PY_SHA256_PREFIX="+digest(newpy))
    print("NO_CHANGES_MADE__GETFILE_REMAINS_BLOCKED")
except Exception as exc:
    print("SAFE_STOP_CLASS="+type(exc).__name__)
    if isinstance(exc,RuntimeError): print("CAUSE="+str(exc)[:100])
    sys.exit(1)
