# -*- coding: utf-8 -*-
"""Verify the 4.2 fix numerically. Two independent tests:

A) recovered passive values vs the gold xlsx (column 'На 30 июня 2026 г.' = values[0]);
B) cross-document: the 2026 report's comparative column 'На 31 декабря 2024 г.'
   must equal the 2025 report's own 'На 31 декабря 2024 г.' column.
Test B is independent of the gold file, so it catches invention.
"""
import sys, os, io, json, re
sys.path.insert(0, r'D:\models\pylibs')
import openpyxl

EX = r'D:\models\extracted'
CODES = ['1300', '1310', '1370', '1400', '1410', '1420', '1450', '1500',
         '1510', '1520', '1530', '1540', '1600', '1700']


def vals(doc, code):
    p = os.path.join(EX, doc + '.json')
    if not os.path.exists(p):
        return None
    j = json.load(io.open(p, encoding='utf-8'))
    res = []
    def walk(items):
        for it in items or []:
            if str(it.get('code')) == code:
                v = it.get('values') or []
                if v:
                    res.append(v)
            walk(it.get('children'))
    walk((j.get('balance') or {}).get('items'))
    return res[0] if res else None


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).replace('\u00a0', ' ').strip()
    if s in ('', '-'):
        return 0 if s == '-' else None
    neg = s.startswith('(')
    d = re.sub(r'\D', '', s)
    return None if not d else (-int(d) if neg else int(d))


wb = openpyxl.load_workbook(os.path.join(EX, 'svod_2025_2026.xlsx'), data_only=True)
ws = wb[wb.sheetnames[0]]
rows = list(ws.iter_rows(values_only=True))
hdr, yrs = rows[0], rows[1]
gold = {}
for r in rows[2:]:
    nm = (r[0] or '').strip() if isinstance(r[0], str) else ''
    if not nm:
        continue
    for ci in range(1, len(hdr)):
        if not hdr[ci]:
            continue
        code = str(hdr[ci]).strip().split(' ')[0].split('+')[0]
        for off, yr in ((0, '2025'), (1, '2026')):
            if ci + off < len(r):
                gold[(nm, code, yr)] = r[ci + off]

print('=== ТЕСТ A: восстановленный пассив против эталона xlsx ===')
ma = mm = 0
for nm, doc in (('КИФА', 'КИФА_6мес_2026'), ('Проект 111', 'Проект 111_6мес_2026')):
    print(f'\n-- {nm} ({doc}), колонка на 30.06.2026')
    for code in CODES:
        g = num(gold.get((nm, code, '2026')))
        v = vals(doc, code)
        jv = num(v[0]) if v else None
        if g is None and jv is None:
            continue
        if g is None:
            verdict = 'в эталоне пусто'
        elif jv is None:
            verdict = 'НЕТ В JSON'; mm += 1
        elif g == jv or (g == 0 and jv is None):
            verdict = 'совпало'; ma += 1
        else:
            verdict = f'РАСХОЖДЕНИЕ {jv - g:+d}'; mm += 1
        print(f'   {code}  эталон={str(g):>10}  JSON={str(jv):>10}  {verdict}')
print(f'\nтест A: совпало {ma}, расхождений {mm}')

print('\n=== ТЕСТ B: колонка 31.12.2024 отчёта 2026 против отчёта 2025 ===')
mb = mmb = 0
for nm, d26, d25 in (('КИФА', 'КИФА_6мес_2026', 'КИФА_6мес_2025'),
                     ('Проект 111', 'Проект 111_6мес_2026', 'Проект 111_6мес_2025')):
    print(f'\n-- {nm}')
    for code in CODES:
        a, b = vals(d26, code), vals(d25, code)
        if not a or not b or len(a) < 3 or len(b) < 2:
            continue
        x, y = num(a[2]), num(b[1])   # 2026 doc's 3rd column vs 2025 doc's 2nd column
        if x is None and y is None:
            continue
        ok = (x == y)
        mb, mmb = (mb + 1, mmb) if ok else (mb, mmb + 1)
        print(f'   {code}  отчёт2026[31.12.2024]={str(x):>10}  отчёт2025[31.12.2024]={str(y):>10}  '
              f'{"совпало" if ok else "РАСХОЖДЕНИЕ"}')
print(f'\nтест B: совпало {mb}, расхождений {mmb}')

print('\n=== ТЕСТ C: арифметика внутри восстановленного баланса ===')
mc = mmc = 0
for doc in ('КИФА_6мес_2026', 'Проект 111_6мес_2026'):
    for col in range(3):
        def g(code):
            v = vals(doc, code)
            return num(v[col]) if v and col < len(v) else None
        s = sum(x for x in (g('1300'), g('1400'), g('1500')) if x is not None)
        ok = g('1700') is not None and abs(s - g('1700')) <= 2 and g('1600') == g('1700')
        mc, mmc = (mc + 1, mmc) if ok else (mc, mmc + 1)
        print(f'   {doc} колонка {col}: 1300+1400+1500={s}  1600={g("1600")}  1700={g("1700")}  '
              f'{"ok" if ok else "FAIL"}')
print(f'\nтест C: ok {mc}, провалено {mmc}')
