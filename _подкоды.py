# -*- coding: utf-8 -*-
r"""Масштаб дефекта «код = 4 цифры + номер подстроки» в СЫРЫХ ответах моделей.

Документ печатает подстроки кодом из 5 цифр: 1530 -> 15301/15302/15303, 1520 -> 15208.
Для 15301 это безобидно (префикс 1530 есть, строка уходит в дети 1530). Опасен случай,
когда модель выбрасывает САМУ строку-префикс: тогда 15208 остаётся отдельной строкой и
наши проверки её не видят, а раздел теряет итог (у «ИПС_6мес_2025» потеряно 1520 = 15307).

Считает по всем сырым кэшам ответов моделей (баланс): сколько строк верхнего уровня имеют
код из 5 цифр с известным префиксом, и есть ли рядом строка-префикс. Денег не тратит.
"""
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

PAGES = r'D:\models\extracted\pages'
rows = []
for f in glob.glob(os.path.join(PAGES, '_llm_*balance*.json')):
    try:
        j = json.load(io.open(f, encoding='utf-8'))
    except Exception:
        continue
    items = j.get('items') or []
    if not items:
        continue
    codes = {str(it.get('code')) for it in items if it.get('code')}
    for it in items:
        c = str(it.get('code') or '')
        if re.fullmatch(r'\d{5}', c) and c[:4] in P.KNOWN_TOP:
            rows.append({'file': os.path.basename(f), 'code': c, 'prefix': c[:4],
                         'has_prefix': c[:4] in codes,
                         'values': it.get('values'),
                         'name': (it.get('name') or '')[:34]})

print(f'сырых кэшей с такими строками: {len(set(r["file"] for r in rows))}')
print(f'всего строк верхнего уровня вида 4+1 цифра: {len(rows)}')
bad = [r for r in rows if not r['has_prefix']]
print(f'из них БЕЗ строки-префикса рядом (потеря итога раздела): {len(bad)}')
print()
for r in rows:
    mark = '  <-- ПРЕФИКСА НЕТ' if not r['has_prefix'] else ''
    print(f"  {r['file'][:52]:52} {r['code']} (префикс {r['prefix']}) "
          f"{r['values']} | {r['name']}{mark}")
