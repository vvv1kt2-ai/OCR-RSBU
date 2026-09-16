# -*- coding: utf-8 -*-
r"""Остаточные провалы под новым кодом: настоящие или ложные?

Ложный провал — самый дорогой вид дефекта: он не портит данные, но покупает эскалацию.
Здесь разбираем каждый остаточный провал по существу: печатаем итог, слагаемые и то, чего
в правиле НЕ ХВАТАЕТ. Вызовов моделей нет.
"""
import copy
import io
import json
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

EX = r'D:\models\extracted'
DOCS = ['Корпсан_6мес_2026', 'ИПС_6мес_2025', 'Моторные технологии_6мес_2025',
        'Эфферон_6мес_2025', 'Органик парк_6мес_2025', 'ТГК-14_6мес_2025',
        'Простая еда_6мес_2025', 'ИПС_6мес_2026', 'ТГК-14_6мес_2026']

PARTS = {
    '1100': ('1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180', '1190'),
    '1200': ('1210', '1215', '1220', '1230', '1240', '1250', '1260'),
    '1400': ('1410', '1420', '1430', '1440', '1450'),
    '1500': ('1510', '1520', '1530', '1540', '1550'),
}


def as_new_code(items, form_key):
    top = {it.get('code') for it in items if it.get('code')}
    out = []
    for it in items:
        cur = dict(it); cur['children'] = list(it.get('children') or [])
        kids, keep = [], []
        for ch in cur['children']:
            c = ch.get('code')
            (kids if (c and c in top) else keep).append(ch)
        cur['children'] = keep; out.append(cur); out.extend(kids)
    out = P.merge_duplicate_codes(out, [], form_key)
    if form_key == 'balance':
        P._assign_bal_codes(out)
    return out


for doc in DOCS:
    p = os.path.join(EX, doc + '.json')
    if not os.path.exists(p):
        print(f'{doc}: нет артефакта'); continue
    j = json.load(io.open(p, encoding='utf-8'))
    for fk in ('balance', 'income_statement', 'cash_flow'):
        items = (j.get(fk) or {}).get('items') or []
        if not items:
            continue
        new = as_new_code(copy.deepcopy(items), fk)
        bad = [c for c in P.run_checks(fk, new)
               if not c['ok'] and any(v is False for v in c['per_column'])]
        if not bad:
            continue
        print(f'=== {doc} / {fk}')
        m = P.val_map(new)
        for c in bad:
            cols = [i for i, v in enumerate(c['per_column']) if v is False]
            print(f"  ВАЛИТ {c['rule'][:46]}  колонки {cols}")
            total = c['rule'][:4]
            if total in PARTS:
                for i in cols:
                    tv = (m.get(total) or [None] * 4)[i]
                    add = [(k, (m.get(k) or [None] * 4)[i]) for k in PARTS[total]]
                    s = sum(v for _, v in add if v is not None)
                    miss = [k for k, v in add if v is None]
                    print(f"     кол.{i}: {total}={tv} сумма={s} разница="
                          f"{(tv - s) if tv is not None else None} пусто={miss}")
        print()
