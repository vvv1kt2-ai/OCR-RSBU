# -*- coding: utf-8 -*-
"""Cross-check: does the xlsx snapshot equal the live catalog for the models we
care about? Any difference means the file is stale. Numeric, not by eye."""
import sys, io, json, hashlib
sys.path.insert(0, r'D:\models\pylibs')
import openpyxl

XL = r'D:\models\plusvibe-prices-2026-09-12.xlsx'
cat = json.load(io.open(r'D:\models\_pv_catalog.json', encoding='utf-8'))

wb = openpyxl.load_workbook(XL, data_only=True, read_only=True)
ws = wb['Текстовые модели']
rows = [list(r) for r in ws.iter_rows(values_only=True)]
wb.close()
hi = next(i for i, r in enumerate(rows) if r[0] and str(r[0]).strip() == 'Модель')


def s(v):
    return '' if v is None else str(v).strip()


file_rows = {}
for r in rows[hi + 1:]:
    mid = s(r[3])
    if not mid:
        continue
    file_rows[mid] = (r[4], r[5], r[6])

live = {}
for m in cat:
    for v in m.get('variants') or []:
        a = str(v.get('addressAs') or '')
        if a:
            live[a] = (v.get('inputRub'), v.get('outputRub'), v.get('cachedInputRub'))

print(f'строк в файле: {len(file_rows)}; адресов в каталоге: {len(live)}')
same = diff = only_file = only_live = 0
diffs = []
for a, (fi, fo, fc) in file_rows.items():
    if a not in live:
        only_file += 1
        continue
    li, lo, lc = live[a]
    if (fi, fo) == (li, lo):
        same += 1
    else:
        diff += 1
        diffs.append((a, fi, fo, li, lo))
only_live = len([a for a in live if a not in file_rows])

print(f'совпало цен: {same}; расходится: {diff}; только в файле: {only_file}; '
      f'только в каталоге: {only_live}')
for d in diffs[:20]:
    print('   ', d)

# сколько адресов вообще раскрывают провайдера
print('\nадреса без скрытого суффикса (вариант по умолчанию):',
      len([a for a in live if ':' not in a]))
print('адресов с явным :alias:', len([a for a in live if ':' in a]))
