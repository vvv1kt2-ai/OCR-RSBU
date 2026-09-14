# -*- coding: utf-8 -*-
"""For the truncated-balance documents: compare raw struct caches vs final JSON balance."""
import os, re, json, glob

PAGES = r'D:\models\extracted\pages'
EX = r'D:\models\extracted'
DOCS = ['Проект 111_6мес_2025', 'Проект 111_6мес_2026', 'КИФА_6мес_2026', 'Эфферон_6мес_2025']

print('=== cache artifacts per document ===')
for d in DOCS:
    hits = sorted([os.path.basename(f) for f in glob.glob(os.path.join(PAGES, f'*{d}*'))])
    print(f'\n--- {d} ({len(hits)} artifacts) ---')
    for h in hits:
        p = os.path.join(PAGES, h)
        sz = os.path.getsize(p)
        print(f'   {h:78} {sz:8}B')

print('\n\n=== struct_balance caches: item count and last code ===')
for f in sorted(glob.glob(os.path.join(PAGES, '*_struct_balance*.json')) + glob.glob(os.path.join(PAGES, '*_tstruct_balance*.json'))):
    b = os.path.basename(f)
    raw = open(f, encoding='utf-8').read()
    try:
        d = json.loads(raw)
        items = d.get('items') or []
        codes = [i.get('code') for i in items]
        print(f'  {b[:66]:66} items={len(items):3} last={codes[-1] if codes else None} json=ok')
    except Exception as e:
        print(f'  {b[:66]:66} size={len(raw)} JSON_INVALID: {str(e)[:60]} tail={raw[-70:]!r}')

print('\n\n=== final JSON balance: where does the array end? ===')
for d in DOCS:
    p = os.path.join(EX, d + '.json')
    j = json.load(open(p, encoding='utf-8'))
    b = j.get('balance') or {}
    items = b.get('items') or []
    codes = [i.get('code') for i in items]
    print(f'  {d:26} items={len(items):3} codes={codes}')
    print(f'  {"":26} warnings={json.dumps(j.get("warnings"), ensure_ascii=False)[:300]}')
