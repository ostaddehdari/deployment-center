from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()

def read(rel:str)->str:
    p=root/rel
    if not p.exists():
        raise SystemExit(f"ERROR: missing {rel}")
    return p.read_text(encoding='utf-8')

def write(rel:str,s:str)->None:
    (root/rel).write_text(s,encoding='utf-8')

def ensure_script_import(rel:str, import_line:str)->None:
    s=read(rel)
    if import_line in s:
        return
    if '<script setup' in s:
        pos=s.find('>\n',s.find('<script setup'))
        if pos<0:
            pos=s.find('>',s.find('<script setup'))
            s=s[:pos+1]+'\n'+import_line+'\n'+s[pos+1:]
        else:
            s=s[:pos+2]+import_line+'\n'+s[pos+2:]
    else:
        s='<script setup lang="ts">\n'+import_line+'\n</script>\n'+s
    write(rel,s)

ensure_script_import(
    'apps/web/components/content/ContentAuthoringShell.vue',
    "import IndexRuntimePanel from '~/components/indexing/IndexRuntimePanel.vue'"
)
ensure_script_import(
    'apps/web/components/indexing/IndexRuntimePanel.vue',
    "import IndexPersonalSelect from '~/components/indexing/IndexPersonalSelect.vue'"
)

for rel in (
    'apps/web/pages/app/create/fiche.vue',
    'apps/web/pages/app/create/sermon.vue',
    'apps/web/pages/app/create/supporting.vue',
    'apps/web/pages/app/content/[id]/edit.vue',
):
    ensure_script_import(rel,"import ContentAuthoringShell from '~/components/content/ContentAuthoringShell.vue'")

ensure_script_import(
    'apps/web/pages/app/content/[id]/indexing.vue',
    "import IndexRuntimePanel from '~/components/indexing/IndexRuntimePanel.vue'"
)

legacy=root/'apps/web/pages/app/indexing/[contentType]/[contentId].vue'
if legacy.exists():
    ensure_script_import(
        'apps/web/pages/app/indexing/[contentType]/[contentId].vue',
        "import IndexRuntimePanel from '~/components/indexing/IndexRuntimePanel.vue'"
    )

print('COMPONENT_RESOLUTION_PATCH=PASS')
