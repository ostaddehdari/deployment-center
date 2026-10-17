"""Authenticated TelTest transfer-job diagnostics and sanitized system logs.

Read-only API. No job dispatching, credentials, raw chats or media.
Registered from the existing operations_center initializer.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

from flask import jsonify
from job_engine import db_connect

BASE = "/teltest"
JOURNAL = Path("/var/lib/teltest/system-logs/latest.json")
UNITS = ("teltest.service", "teltest-delivery.service", "teltest-delivery.timer",
         "teltest-scheduler.service", "teltest-scheduler.timer",
         "teltest-eitaa-gateway.service")


def sanitized(raw, maximum=280):
    value = str(raw or "").replace("\r", " ").replace("\n", " ")
    value = re.sub(r"(?i)(authorization|api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+",
                   r"\1=[REDACTED]", value)
    value = re.sub(r"(?i)\b(bearer)\s+[a-z0-9._~+/-]+", r"\1 [REDACTED]", value)
    value = re.sub(r"(?i)https?://[^\s]+", "[URL]", value)
    value = re.sub(r"(?<!\d)\+?98\d{10}(?!\d)", "[PHONE]", value)
    value = re.sub(r"(?<!\w)gh[psu]_[A-Za-z0-9_]{10,}", "[TOKEN]", value)
    return value[:maximum]


def system_unit(unit):
    # Exact whitelisted unit names. No shell, user-supplied command or sudo.
    if unit not in UNITS:
        return {"state": "unknown", "reason": "unit_not_allowed"}
    try:
        result = subprocess.run(
            ["systemctl", "show", "--no-pager",
             "--property=ActiveState,SubState,Result,ExecMainStatus,NextElapseUSecRealtime,LastTriggerUSec",
             unit], capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode:
            return {"state": "unknown", "reason": "systemctl_unavailable"}
        data = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                name, value = line.split("=", 1)
                if name in {"ActiveState","SubState","Result","ExecMainStatus",
                            "NextElapseUSecRealtime","LastTriggerUSec"}:
                    data[name] = sanitized(value, 90)
        return {"state": data.get("ActiveState","unknown"), "properties": data}
    except (OSError, subprocess.TimeoutExpired):
        return {"state": "unknown", "reason": "systemctl_timeout"}


def journal_events():
    if not JOURNAL.is_file() or JOURNAL.is_symlink():
        return {"available": False, "events": [], "explanation": "system log collector has not produced a snapshot"}
    try:
        # A root-owned collector writes group-readable sanitized information.
        if JOURNAL.stat().st_size > 300_000:
            return {"available": False, "events": [], "explanation": "log snapshot too large"}
        data = json.loads(JOURNAL.read_text(encoding="utf-8"))
        events = []
        for row in (data.get("events") or [])[-100:]:
            if not isinstance(row, dict):
                continue
            unit = str(row.get("unit") or "")
            if unit not in UNITS:
                continue
            events.append({"unit": unit, "when": sanitized(row.get("when"), 40),
                           "level": sanitized(row.get("level"), 20),
                           "message": sanitized(row.get("message"), 260)})
        return {"available": True, "snapshot_at": sanitized(data.get("snapshot_at"), 40),
                "events": events}
    except (ValueError, OSError, TypeError):
        return {"available": False, "events": [], "explanation": "log snapshot unreadable"}


def job_view(conn, job_id):
    job = conn.execute(
        "SELECT id,name,status,selector_type FROM transfer_jobs WHERE id=?",
        (job_id,),).fetchone()
    if job is None:
        return None
    info = dict(job)
    items = dict(conn.execute(
        "SELECT status,COUNT(*) FROM transfer_job_items WHERE transfer_job_id=? GROUP BY status",
        (job_id,)).fetchall())
    counts = {k: int(items.get(k, 0)) for k in
              ("listed","failed","transferred","transferring","uncertain","skipped")}
    counts["total"] = sum(int(x) for x in items.values())
    d = conn.execute("SELECT * FROM delivery_queue WHERE job_id=?", (job_id,)).fetchone()
    queue = {}
    if d is not None:
        source = dict(d)
        for key in ("state","pause_requested","interval_seconds","max_attempts","due_at","updated_at"):
            if key in source:
                queue[key] = source[key]
    errs = []
    for row in conn.execute("""
       SELECT status, attempts, last_error
       FROM transfer_job_items
       WHERE transfer_job_id=? AND last_error IS NOT NULL AND last_error<>''
       ORDER BY updated_at DESC,id DESC LIMIT 18
    """, (job_id,)):
        errs.append({"status": row["status"],"attempts":row["attempts"],
                     "error":sanitized(row["last_error"], 250)})
    internal = []
    for row in conn.execute("""
       SELECT created_at,level,event,message
       FROM operation_job_logs
       WHERE job_kind='transfer' AND job_id=?
       ORDER BY id DESC LIMIT 60
    """, (job_id,)):
        internal.append({"when":sanitized(row["created_at"],40),
                         "level":sanitized(row["level"],20),
                         "event":sanitized(row["event"],70),
                         "message":sanitized(row["message"],290)})
    destination_types = [
        {"provider": sanitized(row[0], 50), "count": row[1]}
        for row in conn.execute(
            "SELECT provider_code,COUNT(*) FROM transfer_destinations "
            "WHERE transfer_job_id=? AND enabled=1 GROUP BY provider_code", (job_id,))
    ]
    if not queue:
        diagnosis = "جاب ایجاد شده اما هنوز وارد صف اجرا نشده است. برای شروع، دکمه «ورود به صف / ادامه» را بزنید."
        code = "NOT_ENQUEUED"
    elif queue.get("state") == "paused" or queue.get("pause_requested"):
        diagnosis = "پردازش این جاب متوقف شده است. از پنل گزینه «ورود به صف / ادامه» را بزنید."
        code = "PAUSED"
    elif queue.get("state") in ("queued","running"):
        diagnosis = "جاب در صف است. وضعیت Worker و لاگ‌های سیستمی را در همین صفحه ببینید."
        code = "QUEUED"
    elif queue.get("state") == "completed":
        diagnosis = "صف این جاب پایان یافته است. تعداد موفق‌ها و موارد ناموفق را بررسی کنید."
        code = "COMPLETED"
    else:
        diagnosis = "وضعیت صف نیازمند بررسی است؛ آخرین خطاها و سرویس‌ها را مشاهده کنید."
        code = "OTHER"
    return {"job": info, "queue": queue, "counts": counts, "errors": errs,
            "events": internal, "destinations": destination_types,
            "diagnosis": diagnosis, "diagnosis_code": code}


def register(app, login_required):
    @app.get(f"{BASE}/api/v2/operations/transfer-jobs/<int:job_id>/system-diagnostics")
    @login_required
    def transfer_job_system_diagnostics(job_id):
        with closing(db_connect()) as conn:
            payload = job_view(conn, job_id)
        if payload is None:
            return jsonify(ok=False, error="جاب انتقال پیدا نشد."), 404
        payload["ok"] = True
        payload["server_at"] = datetime.now(timezone.utc).isoformat()
        payload["systemd"] = {name: system_unit(name) for name in UNITS}
        payload["system_logs"] = journal_events()
        worker = payload["systemd"]["teltest-delivery.timer"].get("state")
        if payload["diagnosis_code"]=="QUEUED" and worker != "active":
            payload["diagnosis"] = "جاب در صف است اما تایمر Worker فعال نیست؛ گزارش سیستم را بررسی کنید."
            payload["diagnosis_code"] = "WORKER_TIMER_INACTIVE"
        return jsonify(payload)
