# -*- coding: utf-8 -*-
"""Positional diff of the свод: csv column i  <->  xlsx column i. Focus on rent columns."""
import os, csv
from openpyxl import load_workbook

EX = r'D:\models\extracted'
rows = list(csv.reader(open(os.path.join(EX, 'svod_2025_2026.csv'), encoding='utf-8-sig'), delimiter=';'))
hdr = [h.strip() for h in rows[0]]
ws = load_workbook(os.path.join(EX, 'svod_2025_2026.xlsx'), data_only=True)['Свод']
h1 = [c.value for c in ws[1]]; h2 = [c.value for c in ws[2]]
xrows = {}
for r in ws.iter_rows(min_row=3, values_only=True):
    if r and r[0] and str(r[0]).strip() not in ('Обозначения:', 'Единица измерения:'):
        xrows[str(r[0]).strip()] = r

# column label from xlsx pair
labels = []
for i in range(1, len(h1)):
    if h1[i] and h2[i]:
        labels.append(f'{h1[i]}_{h2[i]}')
    elif h2[i]:
        labels.append(f'{h1[i-1]}_{h2[i]}')
    else:
        labels.append(None)

print('csv cols:', len(hdr) - 1, 'xlsx labelled cols:', len([l for l in labels if l]))
print(f'\n{"эмитент":22} {"колонка":26} {"csv":>12} {"эталон":>12}')
rent_diffs = 0
all_diffs = 0
for r in rows[1:]:
    name = r[0].strip()
    xr = xrows.get(name)
    if not xr:
        continue
    for i in range(1, min(len(r), len(xr))):
        cv = r[i].strip() if r[i] else ''
        xv = xr[i]
        xvs = '' if xv is None else str(xv).strip()
        if str(cv) != xvs:
            all_diffs += 1
            lbl = hdr[i] if i < len(hdr) else f'col{i}'
            is_rent = 'аренд' in lbl
            if is_rent:
                rent_diffs += 1
            print(f'{name:22} {lbl:26} {cv:>12} {xvs:>12}  {"АРЕНДА" if is_rent else ""}')
print(f'\nвсего расхождений: {all_diffs}; из них по колонкам аренды: {rent_diffs}')
