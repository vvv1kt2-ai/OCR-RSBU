# -*- coding: utf-8 -*-
"""Prove/disprove: escalation artifacts of some docs contain ANOTHER document's data."""
import os, json, glob, re, collections

PAGES = r'D:\models\extracted\pages'
EX = r'D:\models\extracted'

def load(p):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception as e:
        return {'__error__': str(e)}

def kv(obj):
    return {i.get('code'): tuple(i.get('values') or []) for i in (obj.get('items') or []) if i.get('code')}

print('=== A. esc artifacts: expected year (from name) vs actual column dates ===')
for f in sorted(glob.glob(os.path.join(PAGES, '*_esc_balance.json'))):
    b = os.path.basename(f)
    d = load(f)
    m = re.search(r'_6мес_(\d{4})', b)
    want = m.group(1) if m else '?'
    cols = d.get('columns') or []
    first = cols[0] if cols else ''
    got = re.search(r'(\d{4})', first)
    got = got.group(1) if got else '?'
    mark = 'MISMATCH' if (want != '?' and got != '?' and want != got) else 'ok'
    print(f'  {b[:52]:52} name_year={want} col0={first[:28]:28} -> {mark}')

print('\n=== B. pairwise identity of esc artifacts (code->values) ===')
arts = {}
for f in sorted(glob.glob(os.path.join(PAGES, '*_esc_balance.json'))):
    arts[os.path.basename(f)] = kv(load(f))
names = list(arts)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b_ = arts[names[i]], arts[names[j]]
        common = set(a) & set(b_)
        same = [c for c in common if a[c] == b_[c]]
        if len(same) >= 8:
            print(f'  {len(same):3} identical code-values: {names[i][:46]} <-> {names[j][:46]}')

print('\n=== C. cross-year consistency proof for ТГК-14 (code 1210) ===')
t25 = load(os.path.join(EX, 'ТГК-14_6мес_2025.json'))
t26 = load(os.path.join(EX, 'ТГК-14_6мес_2026.json'))
def row(d, code):
    for i in (d.get('balance') or {}).get('items') or []:
        if i.get('code') == code:
            return i
    return None
for code in ('1210', '1150', '1100'):
    r25, r26 = row(t25, code), row(t26, code)
    if not (r25 and r26):
        continue
    print(f'  code {code}')
    print(f'    2025 file cols={t25["balance"]["columns"]}')
    print(f'       ocr1={r25.get("values_ocr1")} final={r25.get("values")}')
    print(f'    2026 file cols={t26["balance"]["columns"]}')
    print(f'       ocr1={r26.get("values_ocr1")} final={r26.get("values")}')
    v25, v26 = r25.get('values') or [], r26.get('values') or []
    o25, o26 = r25.get('values_ocr1') or [], r26.get('values_ocr1') or []
    if len(v25) >= 2 and len(v26) >= 3:
        print(f'    SHARED DATE 31.12.2024 -> final: 2025-file col2={v25[1]} vs 2026-file col3={v26[2]} '
              f'{"CONTRADICTION" if v25[1] != v26[2] else "consistent"}')
    if len(o25) >= 2 and len(o26) >= 3:
        print(f'    SHARED DATE 31.12.2024 -> ocr1 : 2025-file col2={o25[1]} vs 2026-file col3={o26[2]} '
              f'{"CONTRADICTION" if o25[1] != o26[2] else "consistent"}')

print('\n=== D. did corrupted values reach the final свод (csv/xlsx)? ===')
import csv
csvp = os.path.join(EX, 'svod_2025_2026.csv')
rows = list(csv.reader(open(csvp, encoding='utf-8-sig')))
hdr = rows[0]
idx = {h: k for k, h in enumerate(hdr)}
def find_row(name):
    for r in rows[1:]:
        if r and r[0].strip() == name:
            return r
    return None
for comp, code, year, expected in [('ТГК-14', '1210', '2026', '271445'), ('ТГК-14', '1210', '2025', '271445'),
                                   ('Органик парк', '1110', '2025', '270'), ('Органик парк', '1100', '2025', '80984')]:
    key = f'{code}_{year}'
    r = find_row(comp)
    if r is None:
        print(f'  {comp} {key}: row not found'); continue
    col = idx.get(key)
    val = r[col] if col is not None else 'NO_COL'
    print(f'  {comp:14} {key}: csv={val!r} (corrupted value expected {expected!r})')
print('\n  csv header sample:', hdr[:6])
