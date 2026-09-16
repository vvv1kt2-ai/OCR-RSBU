# -*- coding: utf-8 -*-
r"""Эффект правил разделов IV и V после правки BAL_NAMES и правил в run_checks.

Считает по всем артефактам баланса, в двух состояниях:
  «как на диске»            — то, что лежит в extracted/*.json (сделано старым кодом);
  «как будет на новом коде» — вложенные дубли подняты на верхний уровень и слиты
                              (merge_duplicate_codes), как это делает новая ветка разбора.

Печатает, сколько документов валит каждое правило и какие именно. Вызовов моделей нет.
"""
import glob
import io
import json
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

EX = r'D:\models\extracted'
SECT = ('1400 == 1410+1420+1430+1440+1450',
        '1500 == 1510+1520+1530+1540+1550')


def lift_and_merge(items, form_key):
    """приблизить артефакт к тому, что даст новый код: дубли-дети -> верхний уровень"""
    out = []
    for it in items:
        cur = dict(it)
        cur['children'] = list(it.get('children') or [])
        kids, keep = [], []
        for ch in cur['children']:
            c = ch.get('code')
            if c and c in P.KNOWN_TOP:
                kids.append(ch)
            else:
                keep.append(ch)
        cur['children'] = keep
        out.append(cur)
        out.extend(kids)
    warns = []
    merged = P.merge_duplicate_codes(out, warns, form_key)
    return merged, warns


rows = []
for path in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(path)
    if b.startswith('_'):
        continue
    try:
        j = json.load(io.open(path, encoding='utf-8'))
    except Exception:
        continue
    bal = j.get('balance') or {}
    items = bal.get('items') or []
    if not items:
        continue
    doc = b[:-5]
    on_disk = P.run_checks('balance', items)
    new_items, warns = lift_and_merge(items, 'balance')
    on_new = P.run_checks('balance', new_items)
    rows.append({'doc': doc, 'disk': on_disk, 'new': on_new, 'warns': len(warns),
                 'rows_disk': len(items), 'rows_new': len(new_items)})

print(f'балансов в артефактах: {len(rows)}')
print()
for label, key in (('как на диске (старый код)', 'disk'), ('как будет на новом коде', 'new')):
    print(f'=== {label}')
    for rule in SECT:
        bad = []
        for r in rows:
            c = next((x for x in r[key] if x['rule'] == rule), None)
            if c and not c['ok'] and any(v is False for v in c['per_column']):
                bad.append((r['doc'], [i for i, v in enumerate(c['per_column']) if v is False]))
        print(f'  {rule}')
        print(f'    валят {len(bad)} документов')
        for doc, cols in bad[:8]:
            print(f'      {doc[:40]:40} колонки {cols}')
    # сводка по всем правилам
    tot = {}
    for r in rows:
        for c in r[key]:
            if not c['ok'] and any(v is False for v in c['per_column']):
                tot.setdefault(c['rule'], []).append(r['doc'])
    print('  все провалы по правилам:')
    for rule, docs in tot.items():
        print(f'    {rule[:52]:52} {len(docs)}')
    print()
