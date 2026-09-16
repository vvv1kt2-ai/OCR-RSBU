# -*- coding: utf-8 -*-
r"""Новый класс дефекта: код не из 4 цифр.

У «ИПС_6мес_2025» в артефакте вместо кода 1520 стоит «15208» — пять цифр. Такой код не
входит в KNOWN_TOP, поэтому строка становится РЕБЁНКОМ (здесь — внутри 1510), а раздел
теряет её значение: сумма раздела V даёт 73272 против итога 88579, недостача 15307 —
ровно значение «Кредиторская задолженность» из транскрипта.

Здесь: сколько таких кодов в артефактах, какие они, и куда ушло значение 15307.
Ничего не меняет, вызовов моделей нет.
"""
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

EX = r'D:\models\extracted'
rows = []
for path in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(path)
    if b.startswith('_'):
        continue
    try:
        j = json.load(io.open(path, encoding='utf-8'))
    except Exception:
        continue
    for form in ('balance', 'income_statement', 'cash_flow'):
        d = j.get(form) or {}
        for it in (d.get('items') or []):
            for rec in [it] + (it.get('children') or []):
                c = rec.get('code')
                if c and not re.fullmatch(r'\d{4}', str(c)):
                    rows.append((b[:-5], form, str(c), rec.get('name'),
                                 rec.get('values'), it.get('code')))

print(f'строк с кодом НЕ из 4 цифр: {len(rows)}')
for doc, form, c, name, vals, parent in rows:
    print(f'  {doc[:32]:32} {form[:8]:8} код {c!r} внутри {parent} | {(name or "")[:34]} | {vals}')

print()
print('гипотеза: код = настоящий 4-значный + лишняя цифра. Проверяем префиксы:')
for doc, form, c, name, vals, parent in rows:
    for cut in (4, 5):
        pref = c[:cut]
        if pref in P.KNOWN_TOP:
            print(f'  {doc[:30]:30} {c!r} -> {pref} (в KNOWN_TOP) | {(name or "")[:30]}')

print()
print('куда ушло 15307 у «ИПС_6мес_2025»: ищем число во всём артефакте')
j = json.load(io.open(os.path.join(EX, 'ИПС_6мес_2025.json'), encoding='utf-8'))
blob = json.dumps(j, ensure_ascii=False)
for needle in ('15307', '15208', '1520'):
    print(f'  вхождений {needle!r}: {blob.count(needle)}')
