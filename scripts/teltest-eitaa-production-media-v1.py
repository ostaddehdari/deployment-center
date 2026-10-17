#!/usr/bin/env python3
"""Install authenticated Eitaa media + delivery receipts into the LIVE TelTest job.

Only exact-matched 0.12.2 live source layouts are accepted. --check is
nonmutating; --apply backs up and atomically writes changes, restarts TelTest,
leaves Job 11 and all delivery timers paused. Independent EitaaBun gateway
retains internal auth and binds only to 127.0.0.1.
"""
from __future__ import annotations
import argparse, ast, fcntl, os, pathlib, shutil, socket, sqlite3, stat, subprocess, sys, tempfile, time
from urllib.request import urlopen
P=pathlib.Path("/opt/teltest/repo")
G=pathlib.Path("/var/lib/teltest-eitaa-gateway/runtime-v1/src/MainExpress.ts")
HERE=pathlib.Path(__file__).resolve().parent
FILES=("provider_destinations.py","eitaa_user_bridge.py","eitaa_live_gateway.py")
MARKER="TELTEST_EITAA_PRODUCTION_MEDIA_V1"
BACKUP=pathlib.Path("/opt/teltest/backups/eitaa-production-media")
READ_MARK="        // TELTEST_EITAA_VIDEO_READ_SCOPE_V1"
FILE_MARK="        // TELTEST_EITAA_VIDEO_FIRST_CHUNK_V1"
NEW_READ=r"""        // TELTEST_EITAA_PRODUCTION_MEDIA_V1_READ
        // Approved, authenticated account sources. Token validation still
        // applies to all /eitaa/* routes; this does not add a public listener.
        app.use('/eitaa/messages/read', (req, res, next) => {
            const b = req.body || {};
            if (req.method !== 'POST' || b.type !== 'channel'
                || !Number.isSafeInteger(Number(b.id)) || Number(b.id) <= 0
                || !Number.isSafeInteger(Number(b.offset)) || Number(b.offset) <= 0
                || Number(b.offset) > 9999999999
                || !Number.isSafeInteger(Number(b.size))
                || Number(b.size) < 1 || Number(b.size) > 3
                || b.downward === true
                || typeof b.phone !== 'string'
                || !/^\+98[0-9]{10}$/.test(b.phone)) {
                res.status(403).json({error:'Authenticated history scope denied'});
                return;
            }
            next();
        });"""
NEW_FILE=r"""        // TELTEST_EITAA_PRODUCTION_MEDIA_V1_FILE
        // Bounded 512KiB MTProto range reads with the existing private API key.
        // No route is exposed outside the loopback listener.
        app.use('/eitaa/messages/getFile', (req, res, next) => {
            const b = req.body || {};
            const ref = b.file_reference;
            const bytes = ref && typeof ref === 'object' ? Object.values(ref) : [];
            const offset = Number(b.offset);
            const valid = req.method === 'POST' && b.type === 'document'
                && typeof b.phone === 'string'
                && /^\+98[0-9]{10}$/.test(b.phone)
                && /^-?[0-9]{1,25}$/.test(String(b.id || ''))
                && /^-?[0-9]{1,25}$/.test(String(b.access_hash || ''))
                && Number.isSafeInteger(offset) && offset >= 0
                && offset <= 268435456-524288 && offset % 524288 === 0
                && bytes.length > 0 && bytes.length <= 512
                && bytes.every(x => Number.isInteger(x) && x >= 0 && x <= 255);
            if (!valid) {
                res.status(403).json({error:'Authenticated media scope denied'});
                return;
            }
            next();
        });"""

def must(c,msg):
    if not c: raise RuntimeError(msg)
def run(*cmd,timeout=55):
    return subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
def active(unit):return run("systemctl","is-active","--quiet",unit).returncode==0
def guard():
    must(socket.gethostname()=="VMID-20571" and os.geteuid()==0,"WRONG_HOST_OR_USER")
    for unit in ("teltest.service","teltest-eitaa-gateway.service"):
        must(active(unit),"REQUIRED_SERVICE_INACTIVE")
    for unit in ("teltest-delivery.timer","teltest-scheduler.timer","teltest-delivery.service"):
        must(not active(unit),"DELIVERY_TIMERS_MUST_BE_OFF")
    with sqlite3.connect("file:/var/lib/teltest/data/teltest.sqlite3?mode=ro",uri=True) as c:
        c.execute("PRAGMA query_only=ON")
        must(c.execute("SELECT state,pause_requested FROM delivery_queue WHERE job_id=11").fetchone()==("paused",1),"JOB11_NOT_PAUSED")
        must(c.execute("SELECT COUNT(*) FROM delivery_queue WHERE state='running'").fetchone()[0]==0,"QUEUE_RUNNING")
    for file in [G]+[P/f for f in FILES]:
        must(file.is_file() and not file.is_symlink(),"PRODUCTION_FILE_MISSING")
    must((HERE/"eitaa_authenticated_media.py").is_file(),"GITHUB_MEDIA_MODULE_MISSING")
def replace_block(s,start_token,new):
    pos=s.find(start_token)
    must(pos!=-1 and s.count(start_token)==1,"GATEWAY_SCOPE_ANCHOR_CHANGED")
    end=s.find("        });",pos)
    must(end>pos and end-pos<4000,"GATEWAY_SCOPE_END_MISSING")
    return s[:pos]+new+s[end+len("        });"):]
def patched(src):
    a,b,c=(src[x] for x in FILES)
    g=src["MainExpress.ts"]
    for token in ("// TELTEST_EITAA_GATEWAY_ACCESS_CONTROL_V1",
                  "// TELTEST_EITAA_VIDEO_READ_SCOPE_V1",
                  "// TELTEST_EITAA_VIDEO_FIRST_CHUNK_V1",
                  "// TELTEST_EITAA_VIDEO_7084_20_CHUNKS_V1"):
        must(token in g,"GATEWAY_DEPENDENCY_NOT_INSTALLED")
    must("timingSafeEqual" in g and "app.listen(port, '127.0.0.1'" in g,"GATEWAY_AUTH_OR_BINDING_CHANGED")
    must(MARKER not in g and MARKER not in a and MARKER not in b and MARKER not in c,
         "PRODUCTION_MEDIA_ALREADY_INSTALLED")
    g=replace_block(g,READ_MARK,NEW_READ)
    g=replace_block(g,FILE_MARK,NEW_FILE)
    must(g.count("TELTEST_EITAA_PRODUCTION_MEDIA_V1_READ")==1,"GATEWAY_READ_PATCH_FAILED")
    must(g.count("TELTEST_EITAA_PRODUCTION_MEDIA_V1_FILE")==1,"GATEWAY_FILE_PATCH_FAILED")
    head="async def download_eitaa_media(url, tmp_dir, media_index):"
    must(a.count(head)==1,"PROVIDER_DOWNLOADER_ANCHOR_CHANGED")
    a=a.replace(head,"async def _download_eitaa_media_public(url, tmp_dir, media_index):",1)
    wrapper='''# TELTEST_EITAA_PRODUCTION_MEDIA_V1
async def download_eitaa_media(url, tmp_dir, media_index, source_post=None, media_kind=None):
    if source_post is not None:
        from eitaa_authenticated_media import download_eitaa_authenticated
        secure = await download_eitaa_authenticated(
            url, tmp_dir, media_index, source_post, media_kind
        )
        if secure is not None:
            return secure
    return await _download_eitaa_media_public(url, tmp_dir, media_index)


'''
    insert="async def execute_eitaa_destination("
    must(a.count(insert)==1,"PROVIDER_EXECUTOR_MISSING")
    a=a.replace(insert,wrapper+insert,1)
    call='await download_eitaa_media(item["url"], tmp, idx)'
    must(a.count(call)==1,"PROVIDER_MEDIA_CALL_CHANGED")
    a=a.replace(call,'await download_eitaa_media(item["url"], tmp, idx, source_post=row, media_kind=item.get("kind") or row.get("content_type"))',1)
    begin=a.index("async def execute_eitaa_destination(")
    finish=a.index("\nasync def execute_destination(",begin)
    segment=a[begin:finish]
    exception='''            except Exception as exc:
                mark(item_id, "failed", error=f"{type(exc).__name__}: {exc}"[:2000])'''
    must(segment.count(exception)==1,"EXECUTOR_FAILURE_HANDLING_CHANGED")
    exception_fix='''            except Exception as exc:
                from delivery_queue import DeliveryUncertain
                if isinstance(exc, DeliveryUncertain):
                    mark(item_id, "uncertain", error="پاسخ ارسال ایتا نامشخص است؛ بدون تطبیق مقصد تکرار نشود.")
                    raise
                mark(item_id, "failed", error=f"{type(exc).__name__}: {exc}"[:2000])'''
    segment=segment.replace(exception,exception_fix,1)
    # Existing media caption is truncated to 4096 in the gateway; send
    # continuation as receipt-tracked text parts.
    done='''                mark(item_id, "transferred", destination_external_id=result_message_id(sent))'''
    must(segment.count(done)==1,"EXECUTOR_TRANSFER_MARK_CHANGED")
    segment=segment.replace(done,'''                if text and len(text) > 4096:
                    for offset in range(4096, len(text), 4096):
                        sent = await send_external(
                            provider, token, destination["destination_ref"],
                            "text", text[offset:offset+4096], None
                        )
'''+done,1)
    a=a[:begin]+segment+a[finish:]
    bridge_call="item['url'], root, idx, kind, download_eitaa_media"
    must(b.count(bridge_call)==1,"TELEGRAM_EITAA_MEDIA_CALL_CHANGED")
    b=b.replace(bridge_call,"item['url'], root, idx, kind, lambda u,d,n: download_eitaa_media(u,d,n,source_post=row,media_kind=kind)",1)
    orig="return await asyncio.to_thread(send_eitaa,destination_ref,text,downloaded)"
    must(c.count(orig)==1,"EITAA_SEND_PROVIDER_HOOK_CHANGED")
    swap='''# TELTEST_EITAA_PRODUCTION_MEDIA_V1
            from delivery_queue import CURRENT
            session = CURRENT.get(None)
            if session is None:
                return await asyncio.to_thread(send_eitaa,destination_ref,text,downloaded)
            # Mark delivery_parts as 'sending' BEFORE requesting the media upload.
            # A dropped response is uncertain and must never be retried blindly.
            import httpx
            async def transmit():
                receipt = await asyncio.to_thread(send_eitaa,destination_ref,text,downloaded)
                if not isinstance(receipt, dict):
                    raise RuntimeError("EITAA_MEDIA_RECEIPT_INVALID")
                return httpx.Response(200,json={"ok":True,"result":"ok"},
                    request=httpx.Request("POST","https://eitaa-receipt.invalid/"))
            result = await session.send(transmit,kind="http")
            return result.json()'''
    c=c.replace(orig,swap,1)
    # EitaaBun returns {'result':'ok'} only after upload+send; generic dict
    # or a missing status is never an acknowledgement. Fail closed.
    old_ack="if not isinstance(result,dict) or (result.get('result') not in (None,'ok','success') and result.get('ok') is not True):"
    must(c.count(old_ack)==1,"EITAA_SEND_ACK_SHAPE_CHANGED")
    c=c.replace(old_ack,"if not isinstance(result,dict) or not (result.get('result') in ('ok','success') or result.get('ok') is True):",1)
    old="gateway('messages/sendMedia',payload,timeout=180)"
    must(c.count(old)==1,"MEDIA_TIMEOUT_ANCHOR_CHANGED")
    c=c.replace(old,"gateway('messages/sendMedia',payload,timeout=1800)",1)
    for n,src in (("provider_destinations.py",a),("eitaa_user_bridge.py",b),("eitaa_live_gateway.py",c)):
        ast.parse(src,filename=n)
    return {"provider_destinations.py":a,"eitaa_user_bridge.py":b,
            "eitaa_live_gateway.py":c,"MainExpress.ts":g}
def write(path,text,mode):
    fd,tmp=tempfile.mkstemp(prefix="."+path.name+".",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf8") as f:
            f.write(text);f.flush();os.fsync(f.fileno())
        os.chown(tmp,mode.st_uid,mode.st_gid)
        os.chmod(tmp,stat.S_IMODE(mode.st_mode))
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def health():
    try:
        import json
        with urlopen("http://127.0.0.1:18870/teltest/health",timeout=5) as resp:
            x=json.load(resp)
        return x.get("ok") is True and x.get("app")=="teltest"
    except Exception:return False
def main():
    ap=argparse.ArgumentParser()
    q=ap.add_mutually_exclusive_group(required=True)
    q.add_argument("--check",action="store_true");q.add_argument("--apply",action="store_true")
    x=ap.parse_args()
    guard()
    with open("/run/lock/teltest-eitaa-production-media-v1.lock","a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        guard()
        mapping={f:P/f for f in FILES}
        mapping["MainExpress.ts"]=G
        before={name:path.read_text("utf8") for name,path in mapping.items()}
        after=patched(before)
        must(health(),"PRE_INSTALL_HEALTH_FAILED")
        print("PRODUCTION_JOB_PATCH_STAGED=YES")
        print("AUTHENTICATED_VIDEO_AUDIO_DOCUMENT_DOWNLOAD=YES")
        print("PHOTO_AND_TEXT_EXISTING_PATH_PRESERVED=YES")
        print("GATEWAY_PRIVATE_AUTH_BINDING_PRESERVED=YES")
        print("DELIVERY_PARTS_AT_MOST_ONCE=YES")
        print("JOB11_PAUSED=YES")
        if x.check:
            print("DRY_RUN_OK__PRODUCTION_UNCHANGED")
            return
        stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())
        backup=BACKUP/stamp
        backup.mkdir(parents=True,mode=0o700,exist_ok=False)
        module=P/"eitaa_authenticated_media.py"
        must(not module.exists(),"MEDIA_MODULE_ALREADY_EXISTS")
        oldstats={n:p.stat() for n,p in mapping.items()}
        for name,p in mapping.items():shutil.copy2(p,backup/name)
        touched=[]
        try:
            for name,path in mapping.items():
                write(path,after[name],oldstats[name])
                touched.append(name)
            owner=oldstats["provider_destinations.py"]
            data=(HERE/"eitaa_authenticated_media.py").read_text("utf8")
            ast.parse(data)
            fd,tmp=tempfile.mkstemp(prefix=".eitaa-auth-media.",dir=P)
            try:
                with os.fdopen(fd,"w",encoding="utf8") as out:out.write(data);out.flush();os.fsync(out.fileno())
                os.chown(tmp,owner.st_uid,owner.st_gid);os.chmod(tmp,0o644)
                os.replace(tmp,module)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            for service in ("teltest-eitaa-gateway.service","teltest.service"):
                must(run("systemctl","restart",service,timeout=90).returncode==0,"RESTART_FAILED")
            must(health(),"POST_DEPLOY_HEALTH_FAILED")
            guard()
            print("DEPLOY_OK=TELTEST_EITAA_PRODUCTION_MEDIA_V1")
            print("BACKUP="+str(backup))
            print("DELIVERY_TIMERS_LEFT_INACTIVE=YES")
        except Exception:
            print("PRODUCTION_PATCH_ROLLBACK_STARTED")
            for n in touched:
                try:write(mapping[n],before[n],oldstats[n])
                except Exception:pass
            module.unlink(missing_ok=True)
            for svc in ("teltest-eitaa-gateway.service","teltest.service"):
                run("systemctl","restart",svc,timeout=90)
            print("ROLLBACK_ATTEMPTED_BACKUP="+str(backup))
            raise
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("SAFE_STOP_ERROR_CLASS="+type(exc).__name__)
        if isinstance(exc,RuntimeError):print("SAFE_STOP_REASON="+str(exc)[:130])
        sys.exit(1)
