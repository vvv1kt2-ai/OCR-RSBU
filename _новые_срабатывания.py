# -*- coding: utf-8 -*-
r"""Пять НОВЫХ срабатываний правил разделов IV и V: настоящий дефект или ложная тревога?

Новые правила ловят то, что раньше не проверял никто. Но правило, которое валится на
ровном месте, покупает эскалацию — то есть деньги. Поэтому каждое новое срабатывание надо
разобрать по существу: какой итог, какая сумма, на сколько расходится и какая строка
пропала. Вызовов моделей нет.
"""
import copy
import glob
import io
import json
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

EX = r'D:\models\extracted'
DOCS = ['Афанасий_6мес_2025', 'Моторные технологии_6мес_2025', 'Органик парк_6мес_2025',
        'ТГК-14_6мес_2025', 'Эфферон_6мес_2025', 'ИПС_6мес_2025', 'Корпсан_6мес_2026']
RULES = {'1400': ('1400', ('1410', '1420', '1430', '1440', '1450')),
         '1500': ('1500', ('1510', '1520', '1530', '1540', '1550'))}


def as_new_code(items):
    out = []
    for it in items:
        cur = dict(it)
        cur['children'] = list(it.get('children') or [])
        kids, keep = [], []
        for ch in cur['children']:
            c = ch.get('code')
            (kids if (c and c in P.KNOWN_TOP) else keep).append(ch)
        cur['children'] = keep
        out.append(cur)
        out.extend(kids)
    out = P.merge_duplicate_codes(out, [], 'balance')
    P._assign_bal_codes(out)
    lifted = []
    for it in out:
        keep, kids = [], []
        for ch in it.get('children') or []:
            c = ch.get('code')
            (kids if (c and c in P.KNOWN_TOP) else keep).append(ch)
        it['children'] = keep
        lifted.extend(kids)
    out.extend(lifted)
    return out


for doc in DOCS:
    path = os.path.join(EX, doc + '.json')
    if not os.path.exists(path):
        print(f'{doc}: артефакта нет')
        continue
    j = json.load(io.open(path, encoding='utf-8'))
    items = (j.get('balance') or {}).get('items') or []
    if not items:
        print(f'{doc}: баланса нет')
        continue
    new = as_new_code(copy.deepcopy(items))
    m = P.val_map(new)
    print(f'=== {doc}')
    for total, parts in RULES.values():
        tv = m.get(total)
        if not tv:
            continue
        for c in range(len(tv)):
            if tv[c] is None:
                continue
            add = [(p, (m.get(p) or [None] * len(tv))[c] if c < len(m.get(p, [])) else None)
                   for p in parts]
            have = [(p, v) for p, v in add if v is not None]
            s = sum(v for _, v in have)
            if abs(tv[c] - s) > 2:
                print(f'  кол.{c}: {total} = {tv[c]}, сумма {s}, расхождение {tv[c]-s:+}')
                print(f'     слагаемые: ' + ', '.join(f'{p}={v}' for p, v in have))
                print(f'     ПУСТО: {", ".join(p for p, v in add if v is None)}')
    print()
