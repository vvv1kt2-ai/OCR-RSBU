# -*- coding: utf-8 -*-
"""Rent rule: for every document, what rent_extract would add, and where the user disagreed."""
import os, json, glob, sys
sys.path.insert(0, r'D:\models')
import importlib.util
spec = importlib.util.spec_from_file_location('svod', r'D:\models\svod.py')
svod = importlib.util.module_from_spec(spec); spec.loader.exec_module(svod)

EX = r'D:\models\extracted'

def load(p):
    return json.load(open(p, encoding='utf-8'))

print('=== 1. rent rows: where they sit, and what rent_extract does with them ===')
print(f'{"документ":30} {"колонка":>4} {"внутри 1450/1550":>17} {"в 1520":>7} {"верхний":>8} {"сумма":>10} {"действие"}')
for p in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(p)
    if b.startswith('_'):
        continue
    d = load(p)
    bal = d.get('balance')
    if not bal:
        continue
    svod.mark_chains(bal)
    for it in svod.walk(bal.get('items')):
        name = it.get('name') or ''
        if not (svod.LEASE_RE.search(name) or svod.LONG_RENT_RE.search(name) or svod.SHORT_RENT_RE.search(name)):
            continue
        if svod.AVANS_RE.search(name):
            continue
        chain = [c for c in (it.get('_chain') or []) if c]
        code = it.get('code')
        for col in (0,):
            v = (it.get('values') or [None])
            v = v[col] if col < len(v) else None
            inside = 'да' if ('1450' in chain or '1550' in chain) else 'нет'
            in1520 = 'да' if ('1520' in chain or code == '1520') else 'нет'
            top = 'да' if not chain else 'нет'
            act = 'НЕ плюсуется' if inside == 'да' else ('плюсуется к 1550' if in1520 == 'да' else 'плюсуется')
            print(f'{b[:30]:30} {col:>4} {inside:>17} {in1520:>7} {top:>8} {str(v):>10} {act}   «{name[:44]}»')

print('\n=== 2. свод: столбцы 1450+аренда / 1550+аренда — csv против эталона xlsx ===')
import csv
from openpyxl import load_workbook
rows = list(csv.reader(open(os.path.join(EX, 'svod_2025_2026.csv'), encoding='utf-8-sig'), delimiter=';'))
hdr = [h.strip() for h in rows[0]]
csvmap = {r[0].strip(): {hdr[i]: r[i] for i in range(1, len(hdr))} for r in rows[1:] if r and r[0].strip()}
ws = load_workbook(os.path.join(EX, 'svod_2025_2026.xlsx'), data_only=True)['Свод']
h1 = [c.value for c in ws[1]]
h2 = [c.value for c in ws[2]]
xmap = {}
for r in ws.iter_rows(min_row=3, values_only=True):
    if not r or not r[0] or str(r[0]).strip() in ('Обозначения:', 'Единица измерения:'):
        continue
    xmap[str(r[0]).strip()] = r
cols = [i for i, v in enumerate(h1) if v and 'аренда' in str(v)]
print('  колонки с арендой:', [(i, h1[i], h2[i]) for i in cols])
for name, cells in csvmap.items():
    for i in cols:
        key = h1[i] + '_' + str(h2[i])
        cv = cells.get(key)
        xr = xmap.get(name)
        xv = xr[i] if xr else None
        if str(cv) != str(xv):
            print(f'  РАСХОЖДЕНИЕ {name:22} {key:24} csv={cv!r} эталон={xv!r}')
