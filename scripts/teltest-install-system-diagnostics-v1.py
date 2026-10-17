#!/usr/bin/env python3
"""Install TelTest Job system diagnostics UI and root-owned systemd log snapshot.

--check: validated static patch only.
--apply: safe production update to operations_center.py, dashboard.html
         plus new static/API files and a separate diagnostic-only systemd timer.
Never touches delivery_queue state, uploads posts or starts delivery timers.
"""
from __future__ import annotations
import argparse
import ast
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path("/opt/teltest/repo")
OPERATIONS = ROOT / "operations_center.py"
DASHBOARD = ROOT / "templates/dashboard.html"
MODULE = ROOT / "teltest_job_system_diagnostics.py"
JS = ROOT / "static/teltest-system-diagnostics.js"
CSS = ROOT / "static/teltest-system-diagnostics.css"
COLLECTOR = Path("/usr/local/libexec/teltest-system-journal-collector.py")
SERVICE = Path("/etc/systemd/system/teltest-system-journal.service")
TIMER = Path("/etc/systemd/system/teltest-system-journal.timer")
SNAP_DIR = Path("/var/lib/teltest/system-logs")
HERE = Path(__file__).resolve().parent
BACKUP = Path("/opt/teltest/backups/job-system-diagnostics")
OP_MARKER = "# TELTEST_JOB_SYSTEM_DIAGNOSTICS_V1"
HTML_MARKER = "<!-- TELTEST_JOB_SYSTEM_DIAGNOSTICS_V1 -->"
SERVICETXT = """[Unit]
Description=TelTest Sanitized System Journal Collector
After=systemd-journald.service

[Service]
Type=oneshot
User=root
Group=root
UMask=0077
ExecStart=/usr/bin/python3 /usr/local/libexec/teltest-system-journal-collector.py
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/var/lib/teltest/system-logs
CapabilityBoundingSet=
RestrictSUIDSGID=true
"""
TIMERTXT = """[Unit]
Description=TelTest System Journal Snapshot Every Minute

[Timer]
OnBootSec=35s
OnUnitInactiveSec=60s
AccuracySec=5s
Unit=teltest-system-journal.service

[Install]
WantedBy=timers.target
"""


def must(yes,why):
    if not yes:raise RuntimeError(why)


def run(*args,timeout=45):
    return subprocess.run(args,capture_output=True,text=True,timeout=timeout)


def active(unit):
    return run("systemctl","is-active","--quiet",unit,timeout=8).returncode == 0


def health():
    try:
        import json
        with urlopen("http://127.0.0.1:18870/teltest/health",timeout=6) as response:
            d=json.load(response)
        return d.get("ok") is True and d.get("app")=="teltest"
    except Exception:
        return False


def health_wait(seconds=100):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if active("teltest.service") and health():
            return True
        time.sleep(2)
    return False


def guard():
    must(socket.gethostname()=="VMID-20571" and os.geteuid()==0,
         "WRONG_HOST_OR_USER")
    must(active("teltest.service"),"TELTEST_SERVICE_INACTIVE")
    for path in (OPERATIONS,DASHBOARD):
        must(path.is_file() and not path.is_symlink(),"PRODUCTION_FILE_UNAVAILABLE")
    for path in (MODULE,JS,CSS,COLLECTOR,SERVICE,TIMER):
        must(not path.exists() and not path.is_symlink(),
             "DIAGNOSTICS_ALREADY_INSTALLED_OR_FILE_CONFLICT")
    for name in ("teltest_job_system_diagnostics.py",
                 "teltest-system-diagnostics.js",
                 "teltest-system-diagnostics.css",
                 "teltest_system_journal_collector.py"):
        must((HERE/name).is_file(),"GITHUB_SOURCE_MISSING_"+name)


def patch(op,html):
    must(OP_MARKER not in op and HTML_MARKER not in html,
         "ALREADY_PATCHED")
    must("def init_operations_center(app, login_required, api_post_required" in op,
         "OPERATIONS_INITIALIZER_NOT_FOUND")
    anchor="    migrated_hashtags = bootstrap_hashtags()"
    must(op.count(anchor)==1,"OPERATION_REGISTRATION_ANCHOR_CHANGED")
    op=op.replace(anchor, anchor+"""
    # TELTEST_JOB_SYSTEM_DIAGNOSTICS_V1
    from teltest_job_system_diagnostics import register as register_system_diagnostics
    register_system_diagnostics(app, login_required)
""",1)
    must(html.count("</body>")==1,"DASHBOARD_HTML_CLOSE_ANCHOR_CHANGED")
    block="""<!-- TELTEST_JOB_SYSTEM_DIAGNOSTICS_V1 -->
<link rel="stylesheet" href="{{ url_for('static', filename='teltest-system-diagnostics.css') }}?v=20261017-syslog-1">
<script defer src="{{ url_for('static', filename='teltest-system-diagnostics.js') }}?v=20261017-syslog-1"></script>
"""
    html=html.replace("</body>",block+"</body>",1)
    ast.parse(op)
    return op,html


def write_bytes(dest, data, original_mode=None):
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix="."+dest.name+".",dir=dest.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data)
            f.flush();os.fsync(f.fileno())
        if original_mode:
            os.chown(tmp,original_mode.st_uid,original_mode.st_gid)
            os.chmod(tmp,stat.S_IMODE(original_mode.st_mode))
        else:
            os.chmod(tmp,0o644)
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def deploy():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check",action="store_true")
    mode.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    guard()
    original={OPERATIONS:OPERATIONS.read_bytes(),DASHBOARD:DASHBOARD.read_bytes()}
    op,html=patch(original[OPERATIONS].decode("utf8"),original[DASHBOARD].decode("utf8"))
    sources={
        OPERATIONS:op.encode("utf8"),
        DASHBOARD:html.encode("utf8"),
        MODULE:(HERE/"teltest_job_system_diagnostics.py").read_bytes(),
        JS:(HERE/"teltest-system-diagnostics.js").read_bytes(),
        CSS:(HERE/"teltest-system-diagnostics.css").read_bytes(),
        COLLECTOR:(HERE/"teltest_system_journal_collector.py").read_bytes(),
        SERVICE:SERVICETXT.encode("utf8"),
        TIMER:TIMERTXT.encode("utf8"),
    }
    ast.parse(sources[MODULE].decode("utf8"))
    ast.parse(sources[COLLECTOR].decode("utf8"))
    node=shutil.which("node")
    if node:
        with tempfile.NamedTemporaryFile(mode="wb",suffix=".js") as temporary:
            temporary.write(sources[JS]);temporary.flush()
            must(run(node,"--check",temporary.name,timeout=20).returncode==0,
                 "DASHBOARD_JAVASCRIPT_SYNTAX_FAILED")
    must(health(),"PRE_DEPLOY_HEALTH_FAILED")
    print("SITE_DIAGNOSTICS_PATCH_STAGED=YES")
    print("PYTHON_AND_DASHBOARD_SYNTAX_OK=YES")
    print("SYSTEMD_JOURNAL_COLLECTOR_ROOT_ONLY=YES")
    print("AUTHENTICATED_JOB_API_AND_REFRESH_UI=YES")
    print("QUEUE_AND_DELIVERY_TIMERS_UNCHANGED=YES")
    if args.check:
        print("CHECK_OK_NO_CHANGES")
        return
    stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())
    backup=BACKUP/stamp
    backup.mkdir(parents=True,exist_ok=False,mode=0o700)
    original_st={p:p.stat() for p in original}
    for path,content in original.items():
        write_bytes(backup/path.name,content)
    modified=[]
    try:
        for path,content in sources.items():
            write_bytes(path,content,original_st.get(path))
            modified.append(path)
        SNAP_DIR.mkdir(parents=True,exist_ok=True)
        must(run("systemctl","daemon-reload").returncode==0,
             "SYSTEMD_DAEMON_RELOAD_FAILED")
        # Diagnostic timer ONLY. Do not start the delivery timer or jobs.
        must(run("systemctl","start","teltest-system-journal.service",timeout=40).returncode==0,
             "DIAGNOSTIC_COLLECTOR_FAILED")
        must(run("systemctl","enable","--now","teltest-system-journal.timer").returncode==0,
             "DIAGNOSTIC_TIMER_ENABLE_FAILED")
        must(run("systemctl","restart","teltest.service",timeout=80).returncode==0,
             "WEB_SERVICE_RESTART_FAILED")
        must(health_wait(100),"WEB_HEALTH_NOT_RESTORED")
        print("INSTALL_OK=TELTEST_JOB_SYSTEM_DIAGNOSTICS_V1")
        print("BACKUP="+str(backup))
        print("WEB_HEALTH_OK=YES")
        print("SYSTEM_JOURNAL_TIMER_ACTIVE="+str(active("teltest-system-journal.timer")))
        print("NO_JOB_ENQUEUED_OR_RESUMED=YES")
    except Exception:
        print("INSTALL_FAILED_ROLLBACK_STARTED")
        run("systemctl","disable","--now","teltest-system-journal.timer")
        for path in reversed(modified):
            if path in original:
                write_bytes(path,original[path],original_st[path])
            else:
                path.unlink(missing_ok=True)
        run("systemctl","daemon-reload")
        run("systemctl","restart","teltest.service",timeout=90)
        print("ROLLBACK_HEALTH="+str(health_wait(80)))
        print("BACKUP="+str(backup))
        raise


if __name__=="__main__":
    try:deploy()
    except Exception as e:
        print("INSTALL_STOP_CLASS="+type(e).__name__)
        if isinstance(e,RuntimeError):print("REASON="+str(e)[:150])
        sys.exit(1)
