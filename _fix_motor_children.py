# -*- coding: utf-8 -*-
r"""Откуда остаток в разделе II у «Моторные технологии_6мес_2025».

Стирание столбца доказано (1600-1100 = values_ocr1 для 1200 во всех колонках), но проверка
тождества раздела II не сходится: кол.0 +14500, кол.1 +87800, кол.2 ровно 0. Остаток в кол.1
есть и там, где НИЧЕГО не стирали, поэтому это отдельный вопрос, а не следствие порчи.

Гипотеза: недостающие суммы лежат во вложенных строках («в том числе») или в коде 1215.
Печатаем все строки с вложенными и полные массивы 1210..1260.
"""
import io, json, os

EX = r'D:\models\extracted'
STEM = 'Моторные технологии_6мес_2025'
j = json.load(io.open(os.path.join(EX, STEM + '.json'), encoding='utf-8'))
items = ((j.get('balance') or {}).get('items')) or []


def num(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    x = str(x).strip().replace(' ', '')
    if x in ('', '-'):
        return None
    neg = x.startswith('(') and x.endswith(')')
    try:
        return (-1 if neg else 1) * float(x.strip('()'))
    except ValueError:
        return None


def f(x):
    return '—' if x is None else ('%g' % x)


print('=== строки раздела II и их вложенные')
for it in items:
    c = str(it.get('code') or '')
    kids = it.get('children') or []
    if c not in ('1210', '1215', '1220', '1230', '1240', '1250', '1260', '1200', '1600', '1100') and not kids:
        continue
    v = it.get('values') or []
    o = it.get('values_ocr1') or []
    print('%-6s %-34s values=[%s]' % (c or '—', (it.get('name') or '')[:34],
                                      ', '.join(f(num(x)) for x in v)))
    if o:
        print('       %-34s ocr1  =[%s]' % ('', ', '.join(f(num(x)) for x in o)))
    for k in kids:
        kv = k.get('values') or []
        print('       └─ %-31s values=[%s]' % ((k.get('name') or '')[:31],
                                               ', '.join(f(num(x)) for x in kv)))

print()
print('=== сумма раздела II с учётом вложенных (все колонки)')
SEC2 = ['1210', '1215', '1220', '1230', '1240', '1250', '1260']
for i in range(3):
    s = 0.0
    parts = []

    def add(name, arr):
        global s
        if i < len(arr):
            x = num(arr[i])
            if x is not None:
                s += x
                parts.append('%s=%s' % (name, f(x)))

    for c in SEC2:
        for it in items:
            if str(it.get('code') or '') == c:
                add(c, it.get('values') or [])
                for k in (it.get('children') or []):
                    add(c + '.child', k.get('values') or [])
    t = None
    for it in items:
        if str(it.get('code') or '') == '1200':
            arr = it.get('values') or []
            t = num(arr[i]) if i < len(arr) else None
    print('кол.%d: 1200=%-10s сумма=%-10s остаток %s' % (i, f(t), f(s), f((t or 0) - s)))
    print('        %s' % ' + '.join(parts))
