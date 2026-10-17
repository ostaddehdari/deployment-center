from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()
p=root/'tests/real-index-builder.test.cjs'
if not p.exists():
    raise SystemExit('ERROR tests/real-index-builder.test.cjs missing')

s=p.read_text(encoding='utf-8')
old='assert.match(panel,/IndexPersonalSelect code="IDX-001"/);'
new='assert.match(panel,/IndexPersonalSelect[^>]*code="IDX-001"/);\n assert.match(panel,/:admin-preview="props.adminPreview"/);'

if new in s:
    print('REAL_BUILDER_PREVIEW_CONTRACT_ALREADY_ALIGNED=YES')
elif old in s:
    s=s.replace(old,new,1)
    p.write_text(s,encoding='utf-8')
    print('REAL_BUILDER_PREVIEW_CONTRACT_PATCHED=YES')
else:
    raise SystemExit('ERROR stale real-index-builder assertion pattern not found')
