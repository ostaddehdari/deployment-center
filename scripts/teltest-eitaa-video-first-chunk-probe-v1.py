#!/usr/bin/env python3
"""Fetch exactly ONE authenticated 512-KiB video chunk in memory; never send or save."""
import importlib.util,json,pathlib,re,socket,sqlite3,sys,hashlib
from urllib.parse import urlsplit
R=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('history',R/'teltest-eitaa-history-route-v1.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
ROOT=pathlib.Path('/opt/teltest/repo')
DB=pathlib.Path('/var/lib/teltest/data/teltest.sqlite3')
ACC=pathlib.Path('/var/lib/teltest/eitaa-accounts/live_accounts.sqlite3')
def connect(p):
    if not p.is_file() or p.is_symlink():raise RuntimeError('DB_NOT_FOUND')
    c=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True)
    c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON')
    return c
def key(raw):
    s=str(raw or '').strip()
    if s.startswith('https://'):
        u=urlsplit(s)
        if u.hostname not in ('eitaa.com','www.eitaa.com'):return ''
        parts=[x for x in u.path.split('/') if x]
        if parts and parts[0]=='s':parts=parts[1:]
        s=parts[0] if parts else ''
    s=s.lstrip('@').split('/')[0].lower()
    return s if re.fullmatch(r'[a-z][a-z0-9_]{2,63}',s) else ''
def run():
    h.guard()
    print('VIDEO_7084_FIRST_CHUNK_MEMORY_ONLY')
    with connect(DB) as c:
        row=c.execute("SELECT source_ref,source_key FROM content_items WHERE connector_code='eitaa' AND external_id='7084' LIMIT 1").fetchone()
        if not row:raise RuntimeError('SOURCE_POST_NOT_IN_LIBRARY')
        names=sorted(set(filter(None,[key(row['source_ref']),key(row['source_key'])])))
    if not names:raise RuntimeError('SOURCE_CHANNEL_KEY_MISSING')
    with connect(ACC) as c:
        matches=c.execute("""
          SELECT c.peer_id,a.phone FROM eitaa_live_channels c
          JOIN eitaa_live_accounts a ON a.profile=c.profile
          WHERE a.status='connected' AND LOWER(LTRIM(c.username,'@')) IN
          (SELECT value FROM json_each(?))
        """,(json.dumps(names),)).fetchall()
    if len(matches)!=1:raise RuntimeError('SOURCE_ACCOUNT_AMBIGUOUS')
    sys.path.insert(0,str(ROOT))
    from eitaa_live_gateway import gateway
    info=matches[0]
    gateway('auth/loadSession',{'phone':info['phone']},timeout=20)
    data=gateway('messages/read',{'phone':info['phone'],'id':int(info['peer_id']),
      'type':'channel','offset':7085,'size':3,'downward':False},timeout=50)
    if not isinstance(data,dict) or not isinstance(data.get('messages'),list):
        raise RuntimeError('HISTORY_INVALID')
    messages=[m for m in data['messages'] if isinstance(m,dict) and m.get('id')==7084]
    if len(messages)!=1:raise RuntimeError('POST_7084_NOT_FOUND')
    doc=(messages[0].get('media') or {}).get('document')
    if not isinstance(doc,dict):raise RuntimeError('VIDEO_DOCUMENT_MISSING')
    kind=str(doc.get('mime_type') or doc.get('mimeType') or '')
    attrs=doc.get('attributes') or []
    video=kind.startswith('video/') or any(
      isinstance(a,dict) and 'video' in str(a.get('_','')).lower() for a in attrs
    )
    if not video:raise RuntimeError('DOCUMENT_IS_NOT_VIDEO')
    size=int(doc.get('size') or 0)
    if size<=0 or size>256*1024*1024:raise RuntimeError('VIDEO_SIZE_OUT_OF_BOUNDS')
    ref=doc.get('file_reference')
    if ref is None:ref=doc.get('fileReference')
    if isinstance(ref,dict):
        try:values=[ref[k] for k in sorted(ref,key=lambda x:int(x))]
        except (ValueError,TypeError):raise RuntimeError('FILE_REFERENCE_UNEXPECTED')
    elif isinstance(ref,list):values=ref
    else:raise RuntimeError('FILE_REFERENCE_UNEXPECTED')
    if not (1<=len(values)<=512 and all(type(x)==int and 0<=x<=255 for x in values)):
        raise RuntimeError('FILE_REFERENCE_INVALID')
    did=str(doc.get('id') or '')
    access=str(doc.get('access_hash') or doc.get('accessHash') or '')
    if not (re.fullmatch(r'-?[0-9]{1,25}',did) and re.fullmatch(r'-?[0-9]{1,25}',access)):
        raise RuntimeError('DOCUMENT_ID_OR_ACCESS_HASH_UNEXPECTED')
    print('POST_7084_VIDEO_DOCUMENT_VALIDATED=YES')
    print('VIDEO_SIZE_DECLARED_BYTES='+str(size))
    print('FILE_REFERENCE_BYTES='+str(len(values)))
    print('FIRST_CHUNK_REQUEST_LIMIT=524288')
    # No destination or send paths are invoked.
    response=gateway('messages/getFile',{'phone':info['phone'],'id':did,
      'access_hash':access,'file_reference':values,'type':'document','offset':0},timeout=90)
    nums=response.get('data') if isinstance(response,dict) else None
    if not isinstance(nums,list) or not (1<=len(nums)<=524288):
        raise RuntimeError('CHUNK_SHAPE_INVALID')
    if not all(type(x)==int and 0<=x<=255 for x in nums):
        raise RuntimeError('CHUNK_VALUES_INVALID')
    b=bytes(nums)
    fmt='MP4' if len(b)>=12 and b[4:8]==b'ftyp' else (
       'WEBM' if b.startswith(bytes.fromhex('1a45dfa3')) else 'UNKNOWN')
    print('FIRST_CHUNK_BYTES='+str(len(b)))
    print('FIRST_CHUNK_MAGIC='+fmt)
    print('FIRST_CHUNK_SHA256='+hashlib.sha256(b).hexdigest())
    print('NO_FILE_WRITTEN_NO_MESSAGE_SENT_JOB11_PAUSED=YES')
    if fmt=='UNKNOWN':
        raise RuntimeError('VIDEO_CHUNK_MAGIC_UNKNOWN')
    print('FIRST_CHUNK_PROBE_OK')
if __name__=='__main__':
    try:run()
    except Exception as exc:
        print('PROBE_FAILED_CLASS='+type(exc).__name__)
        if isinstance(exc,RuntimeError):print('PROBE_REASON='+str(exc)[:90])
        sys.exit(2)
