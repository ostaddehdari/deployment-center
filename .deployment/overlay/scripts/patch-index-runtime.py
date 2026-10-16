from pathlib import Path
import re,sys
root=Path(sys.argv[1] if len(sys.argv)>1 else '.')
app=root/'apps/api/src/app.module.ts'
if not app.exists():
    raise SystemExit('ERROR: apps/api/src/app.module.ts not found')
s=app.read_text(encoding='utf-8')
imp="import {IndexRuntimeModule} from './index-runtime/index-runtime.module';"
if imp not in s:
    pos=s.find('@Module')
    if pos<0:
        raise SystemExit('ERROR: @Module not found in app.module.ts')
    s=s[:pos]+imp+'\n'+s[pos:]
decorator=s[s.find('@Module'):]
if not re.search(r'imports\s*:\s*\[[\s\S]*?\bIndexRuntimeModule\b',decorator):
    m=re.search(r'imports\s*:\s*\[',s)
    if m:
        s=s[:m.end()]+'IndexRuntimeModule,'+s[m.end():]
    else:
        m=re.search(r'@Module\s*\(\s*\{',s)
        if not m:
            raise SystemExit('ERROR: @Module({...}) structure not found in app.module.ts')
        s=s[:m.end()]+'\n  imports:[IndexRuntimeModule],'+s[m.end():]
app.write_text(s,encoding='utf-8')
print('PATCH_APP_MODULE=PASS')
