#!/usr/bin/env python3
"""One-chunk-only authenticated Eitaa video probe gateway patch; no bulk download."""
import argparse,ast,importlib.util,os,pathlib,shutil,sqlite3,socket,stat,sys,time
ROOT=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('history',ROOT/'teltest-eitaa-history-route-v1.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
P_MARK='# TELTEST_EITAA_VIDEO_FIRST_CHUNK_V1'
J_MARK='// TELTEST_EITAA_VIDEO_FIRST_CHUNK_V1'
P_ANCHOR='"messages/dialogs", "messages/read", "messages/send"'
J_ANCHOR="            'POST /eitaa/messages/read',"
SCOPE="""
        // TELTEST_EITAA_VIDEO_FIRST_CHUNK_V1
        // One successful admission per gateway process. Still requires the internal token.
        let videoProbeUsed = false;
        app.use('/eitaa/messages/getFile', (req, res, next) => {
            const b = req.body || {};
            const ref = b.file_reference;
            const vals = ref && typeof ref === 'object' ? Object.values(ref) : [];
            const byteRef = vals.length > 0 && vals.length <= 512 &&
                vals.every(v => Number.isInteger(v) && v >= 0 && v <= 255);
            const ok = req.method === 'POST' &&
                b.type === 'document' && Number(b.offset) === 0 &&
                typeof b.phone === 'string' && /^\\+98[0-9]{10}$/.test(b.phone) &&
                /^[-]?[0-9]{1,25}$/.test(String(b.id || '')) &&
                /^[-]?[0-9]{1,25}$/.test(String(b.access_hash || '')) &&
                byteRef && !videoProbeUsed;
            if (!ok) {
                res.status(403).json({error:'Video probe denied'});
                return;
            }
            videoProbeUsed = true;
            next();
        });
"""
def patch(py,js):
    h.must('# TELTEST_EITAA_VIDEO_READ_ROUTE_V1' in py,'HISTORY_CLIENT_NOT_INSTALLED')
    h.must('// TELTEST_EITAA_VIDEO_READ_SCOPE_V1' in js,'HISTORY_GATEWAY_NOT_INSTALLED')
    h.must(P_MARK not in py and J_MARK not in js,'PROBE_ALREADY_PATCHED')
    h.must(py.count(P_ANCHOR)==1 and js.count(J_ANCHOR)==1,'PATCH_ANCHOR_MISSING')
    h.must(js.count('        app.use(express.json());')==1,'BODY_PARSER_CHANGED')
    h.must('timingSafeEqual' in js and "app.listen(port, '127.0.0.1'" in js,'SECURITY_NOT_VERIFIED')
    py=py.replace(P_ANCHOR,P_ANCHOR.replace('"messages/send"','"messages/getFile", "messages/send"'),1)
    py=py.replace('def gateway(path: str, body: dict, timeout: int = 30) -> dict:',P_MARK+'\n'+'def gateway(path: str, body: dict, timeout: int = 30) -> dict:',1)
    js=js.replace(J_ANCHOR,J_ANCHOR+'\n            \'POST /eitaa/messages/getFile\',',1)
    js=js.replace('        app.use(express.json());','        app.use(express.json());\n'+SCOPE,1)
    ast.parse(py)
    h.must('videoProbeUsed = true' in js and 'Number(b.offset) === 0' in js,'ONE_CHUNK_GUARD_MISSING')
    return py,js
def main():
    ap=argparse.ArgumentParser()
    a=ap.add_mutually_exclusive_group(required=True)
    a.add_argument('--check',action='store_true');a.add_argument('--apply',action='store_true')
    x=ap.parse_args()
    h.guard()
    with open('/run/lock/teltest-eitaa-history-route.lock','a') as lock:
        import fcntl
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        h.guard()
        p0=h.WEB.read_text('utf8');j0=h.RUNTIME.read_text('utf8')
        p1,j1=patch(p0,j0)
        print('ONE_CHUNK_PATCH_STAGED_AND_PYTHON_AST_OK')
        print('GATEWAY_ONE_REQUEST_MAX=YES')
        print('GETFILE_OFFSET_ZERO_ONLY=YES')
        print('JOB11_AND_TIMERS_PAUSED=YES')
        if x.check:
            print('DRY_RUN_OK__PRODUCTION_NOT_MODIFIED')
            return
        from datetime import datetime,timezone
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup=pathlib.Path('/opt/teltest/backups/eitaa-video-first-chunk')/stamp
        backup.mkdir(parents=True,mode=0o700,exist_ok=False)
        sp=h.WEB.stat();sj=h.RUNTIME.stat()
        shutil.copy2(h.WEB,backup/'eitaa_live_gateway.py')
        shutil.copy2(h.RUNTIME,backup/'MainExpress.ts')
        touched=False
        try:
            h.write_like(h.WEB,p1,sp);touched=True
            h.write_like(h.RUNTIME,j1,sj)
            for svc in ('teltest-eitaa-gateway.service','teltest.service'):
                h.must(h.run(['systemctl','restart',svc],timeout=45).returncode==0,'SERVICE_RESTART_FAILED')
            h.must(h.check_service(),'POST_DEPLOY_HEALTH_FAILED')
            print('DEPLOY_OK=EITAA_VIDEO_FIRST_CHUNK_V1')
            print('BACKUP='+str(backup))
            print('JOB11_AND_TIMERS_STILL_PAUSED=YES')
        except Exception:
            if touched:
                print('ROLLBACK_ATTEMPT')
                h.write_like(h.WEB,p0,sp);h.write_like(h.RUNTIME,j0,sj)
                for svc in ('teltest-eitaa-gateway.service','teltest.service'):
                    h.run(['systemctl','restart',svc],timeout=45)
            raise
if __name__=='__main__':
    try:main()
    except Exception as e:
        print('SAFE_STOP_CLASS='+type(e).__name__)
        if isinstance(e,RuntimeError):print('REASON='+str(e)[:110])
        sys.exit(1)
