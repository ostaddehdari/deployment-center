#!/usr/bin/env python3
"""GitHub-pinned TelTest Eitaa history route. No video download or sending.

--check: pure dry run.
--apply: atomically edits exactly two allowlists, restricted server-side probe,
         checks services, rolls back code on any failed post-deploy check.
"""
import argparse
import ast
import contextlib
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from urllib.error import HTTPError

WEB = Path('/opt/teltest/repo/eitaa_live_gateway.py')
RUNTIME = Path('/var/lib/teltest-eitaa-gateway/runtime-v1/src/MainExpress.ts')
DB = Path('/var/lib/teltest/data/teltest.sqlite3')
BACKUP_ROOT = Path('/opt/teltest/backups/eitaa-history-route')
JS_ANCHOR = "            'POST /eitaa/messages/dialogs',"
PY_ANCHOR = '"messages/dialogs", "messages/send", "messages/sendMedia"'
JS_MARK = '// TELTEST_EITAA_VIDEO_READ_ROUTE_V1'
PY_MARK = '# TELTEST_EITAA_VIDEO_READ_ROUTE_V1'
SCOPE_MARK = '// TELTEST_EITAA_VIDEO_READ_SCOPE_V1'

JS_SCOPE = """
        // TELTEST_EITAA_VIDEO_READ_SCOPE_V1
        // Temporary metadata-only allowance for source post 7084.
        // This handler runs after express.json and before all Eitaa routes.
        app.use('/eitaa/messages/read', (req, res, next) => {
            const input = req.body || {};
            const id = Number(input.id);
            const offset = Number(input.offset);
            const size = Number(input.size);
            if (req.method !== 'POST' || input.type !== 'channel'
                || !Number.isSafeInteger(id) || id <= 0
                || offset !== 7085 || size !== 3
                || input.downward === true
                || typeof input.phone !== 'string' || !/^\\+98[0-9]{10}$/.test(input.phone)) {
                res.status(403).json({ error: 'History probe scope denied' });
                return;
            }
            next();
        });
"""


def must(ok, label):
    if not ok:
        raise RuntimeError(label)


def run(args, *, timeout=12):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)


def active(s):
    return run(['systemctl','is-active','--quiet',s]).returncode==0


def health():
    try:
        with urlopen('http://127.0.0.1:18870/teltest/health',timeout=4) as resp:
            import json
            val=json.load(resp)
            return resp.status==200 and val.get('ok') is True and val.get('app')=='teltest'
    except Exception:
        return False


def gateway_network():
    ss=run(['ss','-H','-lnt','( sport = :1234 )'])
    return ss.returncode==0 and len(ss.stdout.splitlines())==1 and '127.0.0.1:1234' in ss.stdout


def gateway_unauth():
    try:
        with urlopen('http://127.0.0.1:1234/', timeout=3):
            return False
    except HTTPError as exc:
        return exc.code==401
    except Exception:
        return False


def guard():
    must(socket.gethostname()=='VMID-20571' and os.geteuid()==0,'WRONG_HOST_OR_USER')
    for file in (WEB,RUNTIME,DB):
        must(file.is_file() and not file.is_symlink(), 'REQUIRED_FILE_MISSING_OR_SYMLINK')
    must(active('teltest.service') and active('teltest-eitaa-gateway.service'),'SERVICE_INACTIVE')
    for unit in ('teltest-delivery.timer','teltest-scheduler.timer','teltest-delivery.service'):
        must(not active(unit), 'UNSAFE_TIMER_OR_WORKER_ACTIVE')
    with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        must(db.execute('SELECT state,pause_requested FROM delivery_queue WHERE job_id=11').fetchone()==('paused',1), 'JOB11_NOT_PAUSED')
        must(db.execute("SELECT COUNT(*) FROM delivery_queue WHERE state='running'").fetchone()[0]==0,'DELIVERY_RUNNING')
    must(health(),'TELTEST_HEALTH_FAILED')
    must(gateway_network() and gateway_unauth(),'GATEWAY_AUTH_OR_LOOPBACK_FAILED')


def patch(web,js):
    must('# TELTEST_EITAA_SECURED_CLIENT_V1' in web,'CLIENT_NOT_SECURED')
    must('// TELTEST_EITAA_GATEWAY_ACCESS_CONTROL_V1' in js,'GATEWAY_NOT_SECURED')
    must('const allowedRoutes = new Set([' in js and 'timingSafeEqual' in js,'GATEWAY_AUTH_GUARD_ABSENT')
    must("app.listen(port, '127.0.0.1'" in js,'GATEWAY_BIND_NOT_LOOPBACK')
    for marker in (JS_MARK,SCOPE_MARK): must(marker not in js,'GATEWAY_ALREADY_PATCHED')
    must(PY_MARK not in web,'CLIENT_ALREADY_PATCHED')
    must(js.count(JS_ANCHOR)==1 and web.count(PY_ANCHOR)==1,'UNEXPECTED_ALLOWLIST_SHAPE')
    must(js.count('        app.use(express.json());')==1,'UNEXPECTED_EXPRESS_BODY_PARSE_SHAPE')
    js=js.replace(JS_ANCHOR, JS_ANCHOR+"\n            "+JS_MARK+"\n            'POST /eitaa/messages/read',",1)
    js=js.replace('        app.use(express.json());', '        app.use(express.json());\n'+JS_SCOPE,1)
    web=web.replace(PY_ANCHOR,PY_ANCHOR.replace('"messages/send"','"messages/read", "messages/send"'),1)
    must(web.count('def gateway(path: str, body: dict, timeout: int = 30) -> dict:')==1,'CLIENT_GATEWAY_FUNCTION_ANCHOR_MISSING')
    web=web.replace('def gateway(path: str, body: dict, timeout: int = 30) -> dict:',PY_MARK+'\n'+'def gateway(path: str, body: dict, timeout: int = 30) -> dict:',1)
    ast.parse(web)
    must('POST /eitaa/messages/getFile' not in js and '"messages/getFile"' not in web,'FILE_ROUTE_UNEXPECTEDLY_ALLOWED')
    must('offset !== 7085 || size !== 3' in js,'READ_SCOPE_NOT_PRESENT')
    return web,js


def write_like(dest, contents, st):
    fd,name=tempfile.mkstemp(prefix='.'+dest.name+'.',dir=dest.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as h:
            h.write(contents)
            h.flush();os.fsync(h.fileno())
        os.chown(name,st.st_uid,st.st_gid)
        os.chmod(name,stat.S_IMODE(st.st_mode))
        os.replace(name,dest)
    finally:
        if os.path.exists(name):os.unlink(name)


def check_service():
    for _ in range(12):
        if (active('teltest.service') and active('teltest-eitaa-gateway.service')
            and health() and gateway_network() and gateway_unauth()):
            return True
        time.sleep(1)
    return False


def main():
    a=argparse.ArgumentParser()
    g=a.add_mutually_exclusive_group(required=True)
    g.add_argument('--check',action='store_true')
    g.add_argument('--apply',action='store_true')
    arg=a.parse_args()
    guard()
    fd=os.open('/run/lock/teltest-eitaa-history-route.lock',os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        guard()
        web0=WEB.read_text(encoding='utf8')
        js0=RUNTIME.read_text(encoding='utf8')
        web1,js1=patch(web0,js0)
        print('GATEWAY_RUNTIME_AND_CLIENT_PATCH_STAGED')
        print('ONLY_POST_7084_METADATA_READ_ROUTE_SCOPE=YES')
        print('DOWNLOAD_AND_SENDING_NOT_TOUCHED=YES')
        print('STAGED_PYTHON_AST_OK')
        print('SECURITY_LOOPS_AND_QUEUE_PAUSE_OK')
        print('CURRENT_CODE_HASH_PREFIXES=',hashlib.sha256(web0.encode()).hexdigest()[:12],hashlib.sha256(js0.encode()).hexdigest()[:12])
        if arg.check:
            print('DRY_RUN_OK__PRODUCTION_NOT_MODIFIED')
            return
        stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
        backup=BACKUP_ROOT/stamp
        backup.mkdir(parents=True,exist_ok=False,mode=0o700)
        webst=WEB.stat();jsst=RUNTIME.stat()
        # Backup exact bytes and metadata, no tokens copied.
        shutil.copy2(WEB,backup/'eitaa_live_gateway.py')
        shutil.copy2(RUNTIME,backup/'MainExpress.ts')
        changed=False
        try:
            write_like(WEB,web1,webst)
            changed=True
            write_like(RUNTIME,js1,jsst)
            for unit in ('teltest-eitaa-gateway.service','teltest.service'):
                must(run(['systemctl','restart',unit],timeout=45).returncode==0,'RESTART_FAILED')
            must(check_service(),'AFTER_APPLY_HEALTH_FAILED')
            print('DEPLOY_OK=TELTEST_EITAA_VIDEO_HISTORY_READ_V1')
            print('BACKUP='+str(backup))
            print('GETFILE_ROUTE_STILL_BLOCKED=YES')
            print('JOB11_AND_TIMERS_STILL_PAUSED=YES')
        except Exception:
            if changed:
                print('DEPLOY_FAILED_ROLLBACK_START')
                try:
                    write_like(WEB,web0,webst)
                    write_like(RUNTIME,js0,jsst)
                    for unit in ('teltest-eitaa-gateway.service','teltest.service'):
                        run(['systemctl','restart',unit],timeout=45)
                    print('ROLLBACK_CODE_ATTEMPTED')
                except Exception:
                    print('ROLLBACK_NEEDS_MANUAL_REVIEW')
            print('BACKUP='+str(backup))
            raise


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR_CLASS='+type(exc).__name__)
        if isinstance(exc,RuntimeError): print('ERROR_REASON='+str(exc)[:90])
        sys.exit(1)
