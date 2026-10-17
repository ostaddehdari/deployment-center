from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
rel='apps/web/components/content/ContentAuthoringShell.vue'
p=root/rel
if not p.exists():
    raise SystemExit(f'ERROR: missing {rel}')
s=p.read_text(encoding='utf-8')

old='for(const tree of trees)walk(tree.Projects,0)'
new='for(const tree of trees.value)walk(tree.Projects,0)'
if new not in s:
    if old not in s:
        raise SystemExit('ERROR: expected trees iteration pattern not found')
    s=s.replace(old,new,1)

imp="import HtmlRichEditor from '~/components/content/HtmlRichEditor.vue'"
if imp not in s:
    marker='<script setup lang="ts">\n'
    if marker not in s:
        raise SystemExit('ERROR: script setup marker not found')
    s=s.replace(marker,marker+imp+'\n',1)

p.write_text(s,encoding='utf-8')
print('AUTHORING_REF_PATCH=PASS')
