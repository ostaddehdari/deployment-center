# ZohaOnline v0.2.2 — Authoring Ref Runtime Fix

Browser acceptance after v0.2.1 showed that the standalone indexing page was fixed while Create/Edit remained blank.

Root cause was found in the exact authoring source:

`trees` is declared as a Vue `ref<DriveWorkspaceTree[]>([])`, but the folder-list computed function iterated it as:

`for (const tree of trees)`

Inside script code Vue refs are not auto-unwrapped. Evaluating the create/edit template therefore throws a runtime "trees is not iterable" error and prevents ContentAuthoringShell from rendering.

v0.2.2 changes this to:

`for (const tree of trees.value)`

It also explicitly imports `HtmlRichEditor` so every nested component on the critical create/edit path is explicit.

No database or API schema change is introduced.
