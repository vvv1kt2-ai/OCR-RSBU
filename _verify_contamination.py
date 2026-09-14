# -*- coding: utf-8 -*-
"""Verify the cross-document contamination claim in escalation artifacts."""
import os, json, glob, re

PAGES = r'D:\models\extracted\pages'
EX = r'D:\models\extracted'

def load(p):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception as e:
        return {'__error__': str(e)}

def codes_of(obj):
    return {i.get('code'): i.get('values') for i in (obj.get('items') or []) if i.get('code')}

print('=== 1. escalation artifacts vs their own document ===')
for f in sorted(glob.glob(os.path.join(PAGES, '*_esc_balance.json')) + glob.glob(os.path.join(PAGES, '*_tstruct_balance*.json'))):
    b = os.path.basename(f)
    d = load(f)
    cols = d.get('columns')
    items = len(d.get('items') or [])
    print(f'  {b[:58]:58} items={items:3} columns={cols}')

print('\n=== 2. does the escalation artifact of one doc match ANOTHER doc? ===')
# collect all final JSON balance signatures
sigs = {}
for p in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(p)
    if b.startswith('_'):
        continue
    d = load(p)
    bal = d.get('balance') or {}
    sig = tuple(sorted((i.get('code'), tuple(i.get('values') or [])) for i in (bal.get('items') or []) if i.get('code')))
    if sig:
        sigs[b.replace('.json', '')] = set(sig)

def best_match(codes, exclude):
    hits = []
    for name, sig in sigs.items():
        if name == exclude:
            continue
        inter = len(codes & sig)
        if inter >= 5:
            hits.append((inter, name))
    return sorted(hits, reverse=True)[:3]

for f in sorted(glob.glob(os.path.join(PAGES, '*_esc_balance.json')) + glob.glob(os.path.join(PAGES, '*_tstruct_balance*.json'))):
    b = os.path.basename(f)
    d = load(f)
    own = re.sub(r'^_llm_', '', b)
    for suf in ('.pdf_esc_balance.json', '_tstruct_balance_p1_2.json', '_tstruct_balance.json'):
        own = own.replace(suf, '')
    own = re.sub(r'_tstruct_balance.*$', '', own)
    codes = set((c, tuple(v or [])) for c, v in codes_of(d).items())
    if not codes:
        continue
    m = best_match(codes, own)
    flag = 'CONTAMINATED?' if m and m[0][0] >= 5 else ''
    print(f'  {b[:52]:52} own={own[:26]:26} shared_codes_with={m} {flag}')

print('\n=== 3. did contamination reach the final JSON / svod? (values vs values_ocr1 / corrected_by) ===')
for p in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(p)
    if b.startswith('_'):
        continue
    d = load(p)
    bal = d.get('balance') or {}
    changed = []
    for i in (bal.get('items') or []):
        v = i.get('values'); v1 = i.get('values_ocr1')
        if v1 is not None and v != v1:
            changed.append((i.get('code'), v1, v, i.get('corrected_by')))
    if changed:
        print(f'\n  --- {b} ---')
        for code, v1, v, by in changed[:14]:
            print(f'      code {code}: ocr1={v1} -> final={v} corrected_by={by}')
