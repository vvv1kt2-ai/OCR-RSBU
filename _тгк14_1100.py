# -*- coding: utf-8 -*-
r"""Разбор ТГК-14_6мес_2025: провал правила 1100 настоящий или создан моим преобразованием?

Подозрение: строки «в том числе» внутри кода (детализация) я поднял наверх как дубли, и
merge_duplicate_codes их СЛОЖИЛА, удвоив слагаемое. Проверяем тремя состояниями:
  A) артефакт КАК ЕСТЬ (что видит конвейер сегодня)
  B) после моего преобразования
  C) после преобразования без подъёма детей
и печатаем сами строки с кодом 1170/1110.
"""
import copy
import io
import json
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

EX = r'D:\models\extracted'
PARTS = {
    '1100': ('1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180', '1190'),
    '1200': ('1210', '1215', '1220', '1230', '1240', '1250', '1260'),
    '1400': ('1410', '1420', '1430', '1440', '1450'),
    '1500': ('1510', '1520', '1530', '1540', '1550'),
}


def report(tag, items):
    bad = [c for c in P.run_checks('balance', items)
           if not c['ok'] and any(v is False for v in c['per_column'])]
    print(f'  {tag}: провалов {len(bad)} -> {[c["rule"][:26] for c in bad]}')
    m = P.val_map(items)
    for total in ('1100',):
        tv = m.get(total)
        if not tv:
            continue
        add = [(k, m.get(k)) for k in PARTS[total]]
        have = [(k, v) for k, v in add if v]
        for i in range(len(tv)):
            s = sum(v[i] for _, v in have if i < len(v) and v[i] is not None)
            print(f'     {total} кол.{i}: итог={tv[i]} сумма={s} разница={tv[i]-s:+}')
            print('        ' + ', '.join(f'{k}={v[i]}' for k, v in have))


def rows_with_code(items, code, depth=0):
    for it in items:
        if it.get('code') == code:
            print('      ' + '  ' * depth + f"{code} name={(it.get('name') or '')[:34]!r} "
                  f"values={it.get('values')}")
        rows_with_code(it.get('children') or [], code, depth + 1)


doc = 'ТГК-14_6мес_2025'
j = json.load(io.open(os.path.join(EX, doc + '.json'), encoding='utf-8'))
raw = (j.get('balance') or {}).get('items') or []

print('=== A. артефакт КАК ЕСТЬ')
report('как есть', raw)
for c in ('1170', '1110', '1150'):
    print(f'   строки с кодом {c}:')
    rows_with_code(raw, c)

print('\n=== B. после моего преобразования (с подъёмом дублей-детей)')
top = {it.get('code') for it in raw if it.get('code')}
out = []
for it in raw:
    cur = dict(it); cur['children'] = list(it.get('children') or [])
    kids, keep = [], []
    for ch in cur['children']:
        c = ch.get('code')
        (kids if (c and c in top) else keep).append(ch)
    cur['children'] = keep; out.append(cur); out.extend(kids)
outB = P.merge_duplicate_codes(out, [], 'balance')
report('с подъёмом', outB)
for c in ('1170', '1110'):
    print(f'   строки с кодом {c}:')
    rows_with_code(outB, c)

print('\n=== C. только слияние дублей ВЕРХНЕГО уровня, без подъёма детей')
outC = P.merge_duplicate_codes(copy.deepcopy(raw), [], 'balance')
report('без подъёма', outC)
