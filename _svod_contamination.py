# -*- coding: utf-8 -*-
"""Did contaminated escalation values reach the delivered свод (csv + xlsx)?"""
import os, csv, json
from openpyxl import load_workbook

EX = r'D:\models\extracted'
csvp = os.path.join(EX, 'svod_2025_2026.csv')
xlsxp = os.path.join(EX, 'svod_2025_2026.xlsx')

rows = list(csv.reader(open(csvp, encoding='utf-8-sig'), delimiter=';'))
hdr = rows[0]
print('csv header:', hdr)
print('csv rows:', len(rows))
def cell(rows, hdr, name, key):
    idx = {h.strip(): k for k, h in enumerate(hdr)}
    for r in rows[1:]:
        if r and r[0].strip() == name:
            return r[idx[key.strip()]] if key.strip() in idx else 'NO_COL'
    return 'NO_ROW'

for name, key, corrupted in [('ТГК-14', '1210_2026', '271445'), ('ТГК-14', '1210_2025', '271445'),
                             ('Органик парк', '1110_2025', '270'), ('Органик парк', '1100_2025', '80984')]:
    print(f'  csv {name:14} {key}: {cell(rows, hdr, name, key)!r}   (contaminated value = {corrupted})')

wb = load_workbook(xlsxp, data_only=True)
print('\nxlsx sheets:', wb.sheetnames)
ws = wb[wb.sheetnames[0]]
print('dims:', ws.dimensions, ws.max_row, ws.max_column)
hdr_x = [c.value for c in ws[1]]
print('xlsx header:', hdr_x[:10])
hx = {str(h).strip(): i for i, h in enumerate(hdr_x) if h}
for r in ws.iter_rows(min_row=2, values_only=True):
    if r and str(r[0]).strip() in ('ТГК-14', 'Органик парк'):
        for key, corrupted in [('1210_2025', '271445'), ('1210_2026', '271445'),
                               ('1110_2025', '270'), ('1100_2025', '80984')]:
            if key in hx:
                print(f'  xlsx {str(r[0]).strip():14} {key}: {r[hx[key]]!r}  (contaminated = {corrupted})')
        break

print('\n=== which model corrected which document (values_ocr1 != values) ===')
for f in sorted(os.listdir(EX)):
    if not f.endswith('.json') or f.startswith('_'):
        continue
    d = json.load(open(os.path.join(EX, f), encoding='utf-8'))
    n = 0; by = set()
    for form in ('balance', 'income_statement', 'cash_flow'):
        for i in (d.get(form) or {}).get('items') or []:
            if i.get('values_ocr1') is not None and i.get('values_ocr1') != i.get('values'):
                n += 1; by.add(i.get('corrected_by'))
    if n:
        print(f'  {f[:44]:44} corrected_cells={n:3} by={sorted(x for x in by if x)}')
