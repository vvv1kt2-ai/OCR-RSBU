# -*- coding: utf-8 -*-
r"""ТГК-14_6мес_2025, раздел I: сверка артефакта с ОПЛАЧЕННЫМ транскриптом.

Правило 1100 расходится на 2.2 млн во всех трёх колонках, причём сумма БОЛЬШЕ итога.
Печатаем строки раздела I из артефакта (values и values_ocr1 — что было ДО эскалации)
и строки транскрипта, где встречаются эти коды. Вызовов моделей нет.
"""
import glob
import io
import json
import os
import re
import sys

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
doc = 'ТГК-14_6мес_2025'
CODES = ['1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180', '1190', '1100']

j = json.load(io.open(os.path.join(EX, doc + '.json'), encoding='utf-8'))
items = (j.get('balance') or {}).get('items') or []

print('=== АРТЕФАКТ, раздел I (values | values_ocr1)')
for it in items:
    if it.get('code') in CODES:
        print(f"  {it['code']} {(it.get('name') or '')[:36]:36} "
              f"{str(it.get('values')):34} | {it.get('values_ocr1')}")
    for ch in it.get('children') or []:
        if ch.get('code') in CODES:
            print(f"    └─ {ch['code']} {(ch.get('name') or '')[:32]:32} "
                  f"{str(ch.get('values')):34} | {ch.get('values_ocr1')}")

print('\n=== ОПЛАЧЕННЫЙ ТРАНСКРИПТ: строки с кодами раздела I')
for f in sorted(glob.glob(os.path.join(PAGES, f'{doc}_p*_*.md'))):
    t = io.open(f, encoding='utf-8', errors='replace').read()
    hits = []
    for ln in t.splitlines():
        flat = re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', ln)
        if re.search(r'\|\s*(1110|1120|1130|1140|1150|1160|1170|1180|1190|1100)\s*\|', flat):
            hits.append(ln.strip()[:170])
    if hits:
        print(f'\n  --- {os.path.basename(f)}')
        for h in hits[:14]:
            print('   ', h)
