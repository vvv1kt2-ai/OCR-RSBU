# -*- coding: utf-8 -*-
"""Defect 4.2, step 4: impact on the свод. Which cells does the AUTOMATIC build
leave empty while the gold xlsx (hand-edited) has a value? Focus on the four
documents whose balance lost 1700."""
import sys, os, io, csv, re, json
sys.path.insert(0, r'D:\models\pylibs')
import openpyxl

EX = r'D:\models\extracted'
AFFECTED = ['КИФА_6мес_2026', 'Проект 111_6мес_2026', 'Проект 111_6мес_2025', 'Эфферон_6мес_2025']


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return str(int(v))
    s = str(v).replace('\u00a0', ' ').strip()
    if s in ('', '-'):
        return '0' if s == '-' else None
    neg = s.startswith('(')
    d = re.sub(r'\D', '', s)
    return None if not d else ('-' if neg else '') + str(int(d))


with io.open(os.path.join(EX, 'svod_2025_2026.csv'), encoding='utf-8-sig', newline='') as f:
    rows = list(csv.reader(f, delimiter=';'))
csv_hdr = rows[0]
csv_by_doc = {r[0].strip(): r for r in rows[1:] if r and r[0].strip()}
# header form: '2110_2025', '1550+аренда_2026'
csv_cols = {}
for i, h in enumerate(csv_hdr[1:], start=1):
    m = re.match(r'^(.*)_(\d{4})$', h)
    if m:
        csv_cols[(m.group(1).split('+')[0], m.group(2))] = i

wb = openpyxl.load_workbook(os.path.join(EX, 'svod_2025_2026.xlsx'), data_only=True)
ws = wb[wb.sheetnames[0]]
xrows = list(ws.iter_rows(values_only=True))
hdr, yrs = xrows[0], xrows[1]
xcols = {}
for ci in range(1, len(hdr)):
    if hdr[ci]:
        code = str(hdr[ci]).strip().split(' ')[0].split('+')[0]
        for off in (0, 1):
            if yrs[ci + off] in ('2025', '2026'):
                xcols[ci + off] = (code, str(yrs[ci + off]))

out = io.open(r'D:\models\_d42_impact.md', 'w', encoding='utf-8')
w = out.write
w('# Дефект 4.2 — влияние на свод\n\n')
w('`csv` — свод, собранный автоматически из JSON. `xlsx` — эталон с ручными правками.\n'
  'Строки ниже: эталон заполнен, автоматика пуста → эту цифру кто-то внёс руками.\n\n')

tot = 0
for r in xrows[2:]:
    nm = (r[0] or '').strip() if isinstance(r[0], str) else ''
    if not nm:
        continue
    cr = csv_by_doc.get(nm)
    gaps = []
    for ci, (code, yr) in sorted(xcols.items()):
        xv = num(r[ci] if ci < len(r) else None)
        cvi = csv_cols.get((code, yr))
        cvv = num(cr[cvi]) if (cr and cvi is not None and cvi < len(cr)) else None
        if xv is not None and cvv is None:
            gaps.append((code, yr, xv))
    if gaps:
        tot += len(gaps)
        w(f'\n## {nm} — пусто в автоматике: {len(gaps)}\n\n')
        w('| код | год | эталон | документ |\n|---|---|---|---|\n')
        for code, yr, xv in gaps:
            docs = [d for d in AFFECTED if d.endswith('_' + yr) and nm.split(' ')[0] in d]
            w(f'| {code} | {yr} | {xv} | {docs[0] if docs else ""} |\n')

w(f'\n## Итог\n\nВсего пустых-но-заполненных руками ячеек в своде: **{tot}**.\n')
out.close()
print('пустых ячеек всего:', tot)
