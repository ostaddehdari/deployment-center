#!/usr/bin/env python3
"""Read *only* redacted media metadata near Eitaa post 7084. No download/send.

Requires pinned read-only /messages/read gateway access from history-read-v1.
"""
from __future__ import annotations
import json
import os
import pathlib
import re
import socket
import sqlite3
import sys
from urllib.parse import urlsplit

APP = pathlib.Path('/opt/teltest/repo')
DB = pathlib.Path('/var/lib/teltest/data/teltest.sqlite3')
ACCOUNTS = pathlib.Path('/var/lib/teltest/eitaa-accounts/live_accounts.sqlite3')


def connect(p):
    if not p.is_file() or p.is_symlink():
        raise RuntimeError('DATABASE_MISSING_OR_SYMLINK')
    c = sqlite3.connect('file:'+str(p)+'?mode=ro', uri=True, timeout=8)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA query_only=ON')
    return c


def username(raw):
    s=str(raw or '').strip()
    if s.startswith(('http://','https://')):
        p=urlsplit(s)
        if p.scheme!='https' or (p.hostname or '').lower() not in ('eitaa.com','www.eitaa.com'):
            return ''
        a=[v for v in p.path.split('/') if v]
        if a and a[0]=='s':a=a[1:]
        s=a[0] if a else ''
    s=s.lstrip('@').split('/')[0].lower()
    return s if re.fullmatch(r'[a-z][a-z0-9_]{2,63}',s) else ''


def attr(d,*names):
    if not isinstance(d,dict):return None
    for n in names:
        if n in d:return d[n]
    return None


def safe_media(msg):
    media=msg.get('media') or {}
    if not isinstance(media,dict):return ('NONE',False,False,False,False)
    typ=str(attr(media,'_') or '')[:64]
    doc=attr(media,'document') or {}
    if not isinstance(doc,dict):doc={}
    if not doc and isinstance(attr(media,'webpage'),dict):typ='WEBPAGE'
    attrs=attr(doc,'attributes') or []
    if not isinstance(attrs,list):attrs=[]
    mime=str(attr(doc,'mime_type','mimeType') or '').lower()
    return (re.sub(r'[^a-zA-Z0-9_.-]','',typ)[:45],
            bool(attr(doc,'id')),
            bool(attr(doc,'file_reference','fileReference')),
            mime.startswith('video/') or any(isinstance(a,dict) and 'video' in str(attr(a,'_') or '').lower() for a in attrs),
            bool(attr(doc,'size')))


def main():
    if os.geteuid()!=0 or socket.gethostname()!='VMID-20571':
        raise RuntimeError('WRONG_HOST_OR_USER')
    print('EITAA_POST_7084_HISTORY_METADATA_PROBE_V1')
    with connect(DB) as db:
        row=db.execute("SELECT source_ref, source_key FROM content_items WHERE connector_code='eitaa' AND external_id='7084' LIMIT 1").fetchone()
        if row is None:raise RuntimeError('SOURCE_POST_NOT_FOUND')
        keys=sorted({k for k in [username(row['source_ref']),username(row['source_key'])] if k})
    if not keys:raise RuntimeError('SOURCE_KEY_NOT_RESOLVED')
    with connect(ACCOUNTS) as db:
        matches=db.execute('''
          SELECT c.peer_id, a.phone FROM eitaa_live_channels c
          JOIN eitaa_live_accounts a ON a.profile=c.profile
          WHERE a.status='connected' AND LOWER(LTRIM(c.username,'@')) IN
          (SELECT value FROM json_each(?))
        ''',(json.dumps(keys),)).fetchall()
    print('SOURCE_MATCH_COUNT='+str(len(matches)))
    if len(matches)!=1:
        print('SAFE_STOP_NOT_EXACTLY_ONE_SOURCE_DIALOG')
        return 0
    info=matches[0]
    peer_id=int(info['peer_id'])
    if peer_id<=0:
        print('SAFE_STOP_INVALID_SOURCE_PEER')
        return 0
    sys.path.insert(0,str(APP))
    from eitaa_live_gateway import gateway
    gateway('auth/loadSession',{'phone':info['phone']},timeout=20)
    print('SESSION_RESUME=OK')
    data=gateway('messages/read',{
        'phone':info['phone'],'id':peer_id,'type':'channel',
        'offset':7085,'size':3,'downward':False,
    },timeout=50)
    if not isinstance(data,dict) or not isinstance(data.get('messages'),list):
        raise RuntimeError('INVALID_HISTORY_RESPONSE')
    messages=data['messages']
    print('HISTORY_MESSAGES_RETURNED='+str(len(messages)))
    target=None
    for m in messages[:3]:
        if not isinstance(m,dict):continue
        mid=m.get('id')
        if not isinstance(mid,int):continue
        k,di,fr,vm,sz=safe_media(m)
        print('MESSAGE_ID='+str(mid)+' MEDIA_KIND='+k+' DOC_ID_PRESENT='+str(di)+
              ' FILE_REFERENCE_PRESENT='+str(fr)+' VIDEO_INDICATOR='+str(vm)+
              ' SIZE_PRESENT='+str(sz))
        if mid==7084:target=m
    print('TARGET_POST_7084_FOUND='+('YES' if target else 'NO'))
    if target is None:
        print('NO_MEDIA_DOWNLOAD_OR_SEND_ATTEMPTED')
    else:
        typ,di,fr,vm,sz=safe_media(target)
        print('DOCUMENT_DOWNLOAD_METADATA_READY='+('YES' if di and fr and sz else 'NO'))
    print('PROBE_COMPLETE_READ_ONLY_NO_SECRETS_PRINTED')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print('PROBE_FAILED_CLASS='+type(e).__name__)
        if isinstance(e,RuntimeError):print('PROBE_REASON='+str(e)[:90])
        sys.exit(2)
