#!/usr/bin/env python3
"""Read-only sanitized TelTest/Eitaa video prerequisite audit. No OTP/network/sending."""
import json
import pathlib
import sqlite3
import socket
import subprocess
from urllib.parse import urlsplit

if socket.gethostname() != 'VMID-20571':
    raise SystemExit('ERROR_WRONG_HOST')

root = pathlib.Path('/opt/teltest/repo')
gateway = pathlib.Path('/var/lib/teltest-eitaa-gateway/upstream/repo')
print('VIDEO_PREFLIGHT_READ_ONLY_V1')
for unit in ('teltest.service','teltest-eitaa-gateway.service','teltest-delivery.timer','teltest-scheduler.timer'):
    result=subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True)
    print('UNIT', unit, result.stdout.strip() or 'unknown')

with sqlite3.connect('file:/var/lib/teltest/data/teltest.sqlite3?mode=ro',uri=True) as db:
    db.execute('PRAGMA query_only=ON')
    q=db.execute('SELECT state,pause_requested FROM delivery_queue WHERE job_id=11').fetchone()
    print('JOB11', 'PAUSED' if q==('paused',1) else 'UNSAFE_STATE')
    rows=db.execute("""
      SELECT i.id,c.external_id,c.media_json
      FROM transfer_job_items i JOIN content_items c ON c.id=i.content_id
      WHERE i.transfer_job_id=11 AND i.status='failed' AND c.content_type='video'
      ORDER BY i.id LIMIT 3
    """)
    for item_id, post_id, raw in rows:
        try:
            media=json.loads(raw or '[]')
            entry=media[0] if isinstance(media,list) and media else {}
            host=urlsplit(str(entry.get('url') or '')).hostname if isinstance(entry,dict) else None
            kind=entry.get('kind') if isinstance(entry,dict) else None
            print('VIDEO_ITEM',item_id,'POST',post_id,'MEDIA_COUNT',len(media),'HOST',host,'KIND',kind)
        except Exception:
            print('VIDEO_ITEM',item_id,'POST',post_id,'BAD_MEDIA_JSON')

routes=gateway/'src/web/MessageRoutes.ts'
controller=gateway/'src/web/MessageController.ts'
if routes.is_file() and controller.is_file():
    r=routes.read_text(encoding='utf-8')
    c=controller.read_text(encoding='utf-8')
    print('UPSTREAM_READ_ROUTE_PRESENT', '"/read"' in r and 'readMessage' in c)
    print('UPSTREAM_GETFILE_ROUTE_PRESENT','"/getFile"' in r and 'getFile' in c)
    print('UPSTREAM_DOCUMENT_CHUNK_IMPLEMENTATION_PRESENT','getDocumentFile' in c)
else:
    print('UPSTREAM_SOURCE_MISSING_AT_STAGED_PATH')
bridge=root/'eitaa_live_gateway.py'
if bridge.is_file():
    b=bridge.read_text(encoding='utf-8')
    print('TELTEST_BRIDGE_PRESENT', True)
    print('VIDEO_GETFILE_INTEGRATION_DETECTED', 'messages/getFile' in b or 'getDocumentFile' in b)
else:
    print('TELTEST_BRIDGE_MISSING')
print('DIAGNOSTIC_READ_ONLY_END__NO_SECRETS_OR_MESSAGE_TEXT_PRINTED')
