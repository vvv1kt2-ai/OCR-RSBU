# -*- coding: utf-8 -*-
r"""Два уточнения к остатку провалов.

1) «Простая еда_6мес_2025» — разбор ТЕКСТОВЫЙ (200 dpi транскриптов по балансу нет),
   поэтому смотрим производственным разбором structure_text_form, что он видит в IV и V.
2) «Корпсан_6мес_2026» — печатаем весь блок раздела V из транскрипта: сумма не сходится
   ни со сложением аренды, ни без него, значит в форме есть ещё строка или знак.
"""
import glob
import io
import os
import re
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402
import pymupdf  # noqa: E402

DL = r'D:\data-scraping\downloads'
PAGES = r'D:\models\extracted\pages'
SEC = ('1400', '1410', '1420', '1430', '1440', '1450',
       '1500', '1510', '1520', '1530', '1540', '1550')

print('1) «Простая еда_6мес_2025»: производственный текстовый разбор')
doc = pymupdf.open(os.path.join(DL, 'Простая еда_6мес_2025.pdf'))
fp = P.find_form_pages(doc)
cols, items, warns = P.structure_text_form(doc, fp['balance'], 'balance')
doc.close()
print(f'   страницы формы: {fp.get("balance")}, столбцов: {len(cols)}')
for it in items:
    if it.get('code') in SEC:
        print(f'   {it["code"]} {it.get("values")} | {(it.get("name") or "")[:44]}')
        for ch in it.get('children') or []:
            if ch.get('code'):
                print(f'      CHILD {ch["code"]} {ch.get("values")} | {(ch.get("name") or "")[:36]}')
w = [x for x in warns if 'дубл' in x]
print(f'   предупреждения о дублях: {len(w)}')
for x in w:
    print('     ' + x[:120])

print()
print('2) «Корпсан_6мес_2026»: весь раздел V из транскрипта 200 dpi')
f = sorted(glob.glob(os.path.join(PAGES, 'Корпсан_6мес_2026_p3_200_*_pv_*.md'))) or \
    sorted(glob.glob(os.path.join(PAGES, 'Корпсан_6мес_2026_p3_200_*.md')))
txt = io.open(f[0], encoding='utf-8', errors='replace').read()
inside = False
for ln in txt.splitlines():
    s = re.sub(r'\s+', ' ', ln).strip()
    if re.search(r'Итого по разделу IV|раздел IV', s):
        inside = True
    if inside and s:
        print('   ' + s[:130])
    if re.search(r'Итого по разделу V|раздел V', s):
        inside = False
print()
print('   ищем в транскрипте строки со знаком минус или скобками:')
for ln in txt.splitlines():
    s = re.sub(r'\s+', ' ', ln).strip()
    if re.search(r'\|\s*1[45]\d\d\s*\|', s) and ('-' in s or '(' in s):
        print('   ' + s[:130])
