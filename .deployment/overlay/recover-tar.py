#!/usr/bin/env python3
from pathlib import Path
import os, sys

BLOCK=512
src=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
out.mkdir(parents=True,exist_ok=True)
data=src.read_bytes()

def parse_octal(raw:bytes):
    s=raw.replace(b'\x00',b' ').strip()
    if not s:
        return 0
    try:
        return int(s,8)
    except ValueError:
        return None

def header_checksum_ok(block:bytes):
    stored=parse_octal(block[148:156])
    if stored is None:
        return False
    chk=sum(block[:148])+sum(b'        ')+sum(block[156:])
    return chk==stored

def safe_name(block:bytes):
    name=block[0:100].split(b'\x00',1)[0]
    prefix=block[345:500].split(b'\x00',1)[0]
    raw=(prefix+b'/' if prefix else b'')+name
    try:
        text=raw.decode('utf-8')
    except UnicodeDecodeError:
        return None
    if not text or text.startswith('/'):
        return None
    parts=[p for p in text.split('/') if p not in ('','.')]
    if any(p=='..' for p in parts):
        return None
    return '/'.join(parts)

valid=[]
skipped=[]
offset=0
while offset+BLOCK<=len(data):
    block=data[offset:offset+BLOCK]
    if block==b'\x00'*BLOCK:
        offset+=BLOCK
        continue
    name=safe_name(block)
    size=parse_octal(block[124:136])
    typeflag=block[156:157]
    if name and size is not None and size>=0 and header_checksum_ok(block):
        data_start=offset+BLOCK
        data_end=data_start+size
        if data_end>len(data):
            skipped.append((offset,'truncated-data',name,size))
            offset+=BLOCK
            continue
        valid.append((offset,name,size,typeflag))
        target=(out/name).resolve()
        if out!=target and out not in target.parents:
            raise SystemExit(f'ERROR unsafe output path: {name}')
        if typeflag in (b'0',b'\x00',b'7'):
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data[data_start:data_end])
        elif typeflag==b'5':
            target.mkdir(parents=True,exist_ok=True)
        elif typeflag in (b'1',b'2'):
            skipped.append((offset,'link-skipped',name,size))
        offset=data_start+((size+BLOCK-1)//BLOCK)*BLOCK
    else:
        skipped.append((offset,'invalid-header',name,size))
        offset+=BLOCK

print(f'RECOVERY_VALID_ENTRIES={len(valid)}')
print(f'RECOVERY_SKIPPED_BLOCKS={len(skipped)}')
for item in valid:
    print(f'RECOVERED|{item[1]}|{item[2]}')
for item in skipped[:40]:
    print(f'SKIPPED|offset={item[0]}|reason={item[1]}|name={item[2]}|size={item[3]}')
