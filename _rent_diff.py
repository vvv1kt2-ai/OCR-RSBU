# -*- coding: utf-8 -*-
"""Compare ONLY the rent columns (1450+аренда / 1550+аренда) between csv and the user's xlsx."""
import os, csv
from openpyxl import load_workbook

EX = r'D:\models\extracted'
ws = load_workbook(os.path.join(EX, 'svod_2025_2026.xlsx'), data_only=True)['Свод']
print('xlsx row1:', [c.value for c in ws[1]])
print('xlsx row2:', [c.value for c in ws[2]])

rows = list(csv.reader(open(os.path.join(EX, 'svod_2025_2026.csv'), encoding='utf-8-sig'), delimiter=';'))
hdr = [h.strip() for h in rows[0]]
csvmap = {r[0].strip(): {hdr[i]: r[i] for i in range(1, len(hdr))} for r in rows[1:] if r and r[0].strip()}

h1 = [c.value for c in ws[1]]
h2 = [c.value for c in ws[2]]
xmap = {}
for r in ws.iter_rows(min_row=3, values_only=True):
    if r and r[0] and str(r[0]).strip() not in ('Обозначения:', 'Единица измерения:'):
        xmap[str(r[0]).strip()] = r

rent_cols = [i for i, v in enumerate(h1) if v and 'аренд' in str(v)]
print('\nколонки аренды в xlsx:', [(i, h1[i], h2[i]) for i in rent_cols])
print(f'\n{"эмитент":24} {"колонка":22} {"csv":>12} {"эталон":>12}  {"вердикт"}')
for i in rent_cols:
    code = str(h1[i]); year = str(h2[i])
    key = f'{code}_{year}'
    for name in csvmap:
        cv = csvmap[name].get(key)
        xr = xmap.get(name)
        xv = xr[i] if xr else None
        if str(cv) != str(xv):
            print(f'{name:24} {key:22} {str(cv):>12} {str(xv):>12}  РАСХОЖДЕНИЕ')
print('\n(строк без расхождений не показано)')
