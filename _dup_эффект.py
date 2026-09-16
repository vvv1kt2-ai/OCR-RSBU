# -*- coding: utf-8 -*-
r"""Что правка дублей изменит в СОХРАНЁННЫХ артефактах, если их пересобрать.

Ничего не пишет и не меняет: только читает extracted/*.json и показывает, у кого дубль
верхнеуровневого кода лежит ВЛОЖЕННОЙ строкой (так его прятал прежний разбор), какое
значение стоит сейчас и какое встанет после слияния. Отвечает на вопрос «сколько
документов и на сколько сдвинется свод», не тратя ни копейки.
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
LEASE = re.compile(r'аренд|лизинг', re.I)

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
        items = d.get('items') or []
        top = {it.get('code') for it in items if it.get('code')}
        for it in items:
            for ch in it.get('children') or []:
                c = ch.get('code')
                if c and c in P.KNOWN_TOP and c in top:
                    cur = [x for x in items if x.get('code') == c][-1]
                    rows.append((b[:-5], form, c, cur.get('name'), cur.get('values'),
                                 ch.get('name'), ch.get('values')))

print(f'документов/форм с вложенным дублем верхнеуровневого кода: {len(rows)}')
for doc, form, c, n1, v1, n2, v2 in rows:
    v1 = v1 or []
    v2 = v2 or []
    merged = P.merge_duplicate_codes(
        [{'code': c, 'name': n1, 'values': v1}, {'code': c, 'name': n2, 'values': v2}])
    lease = ' АРЕНДА' if LEASE.search(n2 or '') else ''
    print(f'  {doc[:32]:32} {form[:8]:8} {c}: {v1} + {v2} -> {merged[0]["values"]}{lease}')
    print(f'      «{(n1 or "")[:38]}» + «{(n2 or "")[:38]}»')
print()
print('Вывод: правка касается только этих строк; остальные значения не меняются.')
