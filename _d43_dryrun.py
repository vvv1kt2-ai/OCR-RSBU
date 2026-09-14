# -*- coding: utf-8 -*-
"""Dry run of the свод rebuild after the 4.3 fix.

Writes NOTHING into extracted/: svod_build's three output paths are redirected to
tmp/. Then the freshly built CSV is diffed cell by cell against the current one.
The gold xlsx is never touched.
"""
import os, sys, io, csv, shutil, hashlib
from pathlib import Path
sys.path.insert(0, r'D:\models')
sys.path.insert(0, r'D:\models\pylibs')

EX = Path(r'D:\models\extracted')
TMP = Path(r'D:\models\tmp\_svod_dry')
TMP.mkdir(parents=True, exist_ok=True)
REAL_CSV = EX / 'svod_2025_2026.csv'
REAL_XLSX = EX / 'svod_2025_2026.xlsx'


def h(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()[:12].upper()


before_csv, before_xlsx = h(REAL_CSV), h(REAL_XLSX)
shutil.copy2(REAL_CSV, TMP / 'csv_before.csv')
print(f'до:  csv={before_csv}  xlsx={before_xlsx}')

import svod_build
svod_build.XLSX_PATH = TMP / 'svod_dry.xlsx'
svod_build.CSV_PATH = TMP / 'svod_dry.csv'
svod_build.AUDIT_PATH = TMP / 'svod_dry_audit.md'
svod_build.main()

after_csv, after_xlsx = h(REAL_CSV), h(REAL_XLSX)
print(f'\nпосле прогона: csv={after_csv}  xlsx={after_xlsx}')
print('реальные файлы не тронуты:', before_csv == after_csv and before_xlsx == after_xlsx)


def load(p):
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.reader(f, delimiter=';'))


old, new = load(REAL_CSV), load(TMP / 'svod_dry.csv')
print(f'\nстрок: было {len(old)}, стало {len(new)}')
hdr = old[0]
diffs = []
for ro, rn in zip(old, new):
    if ro[0] != rn[0]:
        diffs.append((ro[0], 'СТРОКА СДВИНУЛАСЬ', '', ''))
        continue
    for i, (a, b) in enumerate(zip(ro, rn)):
        if a != b:
            diffs.append((ro[0], hdr[i] if i < len(hdr) else f'col{i}', a, b))
print(f'отличий ячеек: {len(diffs)}')
for d in diffs:
    print(f'   {d[0]:22} {d[1]:20} {d[2]!r:>14} -> {d[3]!r}')
