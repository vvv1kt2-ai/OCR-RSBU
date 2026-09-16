# -*- coding: utf-8 -*-
r"""Разбор остатка: три документа, которые падают по разделу V и один по разделу IV.

Смотрим ТРАНСКРИПТЫ (уже оплачены): что форма печатает в разделах IV и V и откуда
расхождение. Правило не должно покупать эскалацию там, где виновато само правило.
"""
import glob
import io
import os
import re
import sys

PAGES = r'D:\models\extracted\pages'
DOCS = {
    'Простая еда_6мес_2025': ('1400', '1500'),
    'ИПС_6мес_2025': ('1500',),
    'Корпсан_6мес_2026': ('1500',),
}
CODES = ('1400', '1410', '1420', '1430', '1440', '1450',
         '1500', '1510', '1520', '1530', '1540', '1550')

for doc, wants in DOCS.items():
    files = sorted(glob.glob(os.path.join(PAGES, f'{doc}_p*_200_*.md')))
    print(f'=== {doc}: страниц транскрипта 200 dpi — {len(files)}')
    for f in files:
        txt = io.open(f, encoding='utf-8', errors='replace').read()
        # строки таблицы, где встречается код раздела
        rows = [ln for ln in txt.splitlines()
                if any(re.search(r'(?<![\d])' + c + r'(?![\d])', ln) for c in CODES)]
        if not rows:
            continue
        print(f'  --- {os.path.basename(f)}')
        for ln in rows:
            s = re.sub(r'\s+', ' ', ln).strip()
            print('     ' + s[:150])
        # отдельно: ищем загадочное число
        for m in re.finditer(r'199788|15307|4000', txt):
            ctx = re.sub(r'\s+', ' ', txt[max(0, m.start() - 90):m.start() + 40]).strip()
            print(f'     [число {m.group(0)}] ...{ctx}')
    print()
