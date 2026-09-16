# -*- coding: utf-8 -*-
r"""Что эскалация ВЕРНУЛА по «Моторные технологии_6мес_2025» (код 1250).

Ключевой вопрос: структурный это дефект или ошибка чтения. Если модель в ответе эскалации
напечатала ОБЕ строки 1250 (4070 «Денежные средства» и 14500 «Депозитные счета») — значит
чтение было верным, а строку потерял НАШ разбор. Тогда эскалация тут не помощник:
сколько её ни запускай, разбор снова оставит одну строку.

Денег не тратит: читает уже оплаченные кэши ответов.
"""
import glob
import io
import json
import os
import sys

PAGES = r'D:\models\extracted\pages'
PATTERNS = ['*Моторные*esc_balance*', '*Моторные*struct_balance*', '*Моторные*tstruct*']

for pat in PATTERNS:
    files = sorted(glob.glob(os.path.join(PAGES, pat)))
    if not files:
        continue
    print(f'=== {pat}: файлов {len(files)}')
    for f in files:
        b = os.path.basename(f)
        try:
            j = json.load(io.open(f, encoding='utf-8'))
        except Exception as e:
            print(f'  {b}: не прочитан ({e})')
            continue
        items = j.get('items') or []
        cols = j.get('columns') or []
        print(f'  --- {b}')
        print(f'      столбцов: {len(cols)}  строк: {len(items)}')
        for it in items:
            c = it.get('code')
            nm = (it.get('name') or '')[:44]
            if c in ('1250', '1200', '1260', '1220', '1230') or 'енежн' in nm or 'епозит' in nm:
                print(f'      {c} {it.get("values")} | {nm}')
    print()
