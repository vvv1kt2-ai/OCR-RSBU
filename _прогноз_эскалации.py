# -*- coding: utf-8 -*-
r"""Прогноз: сколько эскалаций потребует НОВЫЙ код на том же пилоте (0 ₽, без вызовов).

Зачем. Эскалация — 59% цены пилота. Но её запускают ПРОВАЛЫ ПРОВЕРОК, а правила и разбор
мы только что починили: правила IV и V появились, BAL_NAMES дополнены, дубли кодов
сливаются, под-коды пристраиваются к своей строке. Значит спрос на эскалацию должен был
упасть — и это надо измерить, прежде чем браться за длину её вывода.

Как считаем, не тратя денег: артефакт на диске — это результат СТАРОГО кода. Приводим его к
состоянию нового кода офлайн (поднять дубли-коды из детей и слить, расставить коды по
именам новой таблицы и поднять такие строки наверх), затем прогоняем производственный
run_checks. Формы с провалом = кандидаты на эскалацию, как их видит escalate_failed_form.
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
FORMS = ('balance', 'income_statement', 'cash_flow')
# Цены измерены на пилоте (_ЭСКАЛАЦИЯ_ОКУПАЕМОСТЬ.md): расшифровка страницы эскалации
# и один вызов структурирования.
PAGE_RUB = 0.708
STRUCT_RUB = 3.2
MAX_PAGES = 8


def as_new_code(items, form_key):
    """привести артефакт старого кода к состоянию нового разбора

    ВАЖНО, на этом уже обожглись: поднимать наверх можно только ДУБЛИ кодов, то есть
    строки-дети, чей код УЖЕ есть на верхнем уровне. Старый _normalize_llm понижал в
    ребёнка именно второй дубль (свод видит только верхний уровень, и строка терялась) —
    новый код сливает такие строки до понижения. А просто «поднять любого ребёнка с
    известным кодом» нельзя: у «Афанасия_6мес_2025» 1215 = 70/27/53 — законная деталь
    ВНУТРИ 1210 и уже в него включена; подъём удваивал её и рождал ложный провал правила
    1200, которого в данных нет.
    """
    top_codes = {it.get('code') for it in items if it.get('code')}
    out = []
    for it in items:
        cur = dict(it)
        cur['children'] = list(it.get('children') or [])
        kids, keep = [], []
        for ch in cur['children']:
            c = ch.get('code')
            (kids if (c and c in top_codes) else keep).append(ch)
        cur['children'] = keep
        out.append(cur)
        out.extend(kids)
    out = P.merge_duplicate_codes(out, [], form_key)
    if form_key == 'balance':
        P._assign_bal_codes(out)
    return out


def failing_forms(items_by_form):
    out = {}
    for fk in FORMS:
        items = items_by_form.get(fk)
        if not items:
            continue
        chks = P.run_checks(fk, items)
        bad = [c for c in chks if not c['ok'] and any(v is False for v in c['per_column'])]
        if bad:
            out[fk] = bad
    return out


rows = []
for path in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(path)
    if b.startswith('_'):
        continue
    try:
        j = json.load(io.open(path, encoding='utf-8'))
    except Exception:
        continue
    doc = b[:-5]
    old_forms, new_forms = {}, {}
    pages = {}
    esc_touched = False
    for fk in FORMS:
        d = j.get(fk) or {}
        items = d.get('items') or []
        if not items:
            continue
        old_forms[fk] = items
        new_forms[fk] = as_new_code(copy.deepcopy(items), fk)
        pages[fk] = len(d.get('transcript_pages') or [])
        blob = json.dumps(items, ensure_ascii=False)
        if 'corrected_by' in blob or 'confirmed_by' in blob:
            esc_touched = True
    rows.append({'doc': doc, 'old': failing_forms(old_forms),
                 'new': failing_forms(new_forms), 'pages': pages, 'esc': esc_touched})

print(f'документов в выборке: {len(rows)}')


def summarize(key):
    docs = [r for r in rows if r[key]]
    pages = 0
    forms = 0
    for r in docs:
        for fk, bad in r[key].items():
            forms += 1
            pages += min(r['pages'].get(fk, 0), MAX_PAGES)
    cost = pages * PAGE_RUB + forms * STRUCT_RUB
    return docs, forms, pages, cost


for label, key in (('СТАРЫЙ код (артефакты на диске)', 'old'),
                   ('НОВЫЙ код (после правок)', 'new')):
    docs, forms, pages, cost = summarize(key)
    print(f'\n=== {label}')
    print(f'  документов с провалом: {len(docs)}   форм: {forms}   '
          f'страниц к перечитыванию: {pages}   оценка: {cost:.1f} ₽')
    for r in sorted(docs, key=lambda r: -sum(len(v) for v in r[key].values()))[:12]:
        rules = '; '.join(f"{fk}:{len(b)}" for fk, b in r[key].items())
        print(f"    {r['doc'][:38]:38} {rules}")

print()
esc_docs = [r['doc'] for r in rows if r['esc']]
print(f'документов, которых эскалация КОСНУЛАСЬ на пилоте: {len(esc_docs)}')
print('  ' + ', '.join(d[:26] for d in esc_docs[:10]))
