# -*- coding: utf-8 -*-
r"""Что изменилось в данных: новые артефакты против бэкапа + разбор сбоев.

Цена ничего не значит, если данные испортились. Сравниваем значения по каждому документу и
каждой строке между extracted/*.json (прогон V2) и extracted/_backup_v2_before/*.json (V1).

Отдельно считаем полноту формы по замыкающему коду — это то, что реально важно:
баланс 1700, ОФР 2400/2410, ОДДС 4500. Форма без замыкающего кода неполна.

И отдельно — документы, которые в прогоне упали: их артефакт на диске ОСТАЛСЯ СТАРЫМ,
и если этого не знать, легко принять старые данные за результат нового прогона.
"""
import io, json, os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
BAK = os.path.join(OUT, '_backup_v2_before')
TERM = {'balance': ('1700',), 'income_statement': ('2400', '2410'), 'cash_flow': ('4500',)}
NEW = json.load(io.open(r'D:\models\_v2_прогон.json', encoding='utf-8'))
failed = {r['stem'] for r in NEW['rows'] if r['status'] in ('failed', None)}
mtime = {r['stem']: r for r in NEW['rows']}


def load(path):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except Exception:
        return None


def items_map(r, key):
    """{(код, колонка): значение}"""
    d = (r or {}).get(key)
    if not d:
        return {}
    out = {}
    for it in (d.get('items') or []):
        code = str(it.get('code') or '').strip()
        if not code:
            continue
        for i, v in enumerate(it.get('values') or []):
            if v not in (None, ''):
                out[(code, i)] = str(v)
    return out


def has_terminal(r, key):
    codes = {c for c, _ in items_map(r, key)}
    return any(t in codes for t in TERM[key])


stems = sorted(os.path.splitext(f)[0] for f in os.listdir(BAK)
               if f.endswith('.json') and not f.startswith('_'))
print('документов в бэкапе: %d' % len(stems))
print('упали в прогоне (артефакт остался старым): %s' % (sorted(failed) or '—'))
print()

gained = lost = changed = same = 0
term_regress = []
tot_new = tot_old = 0
for stem in stems:
    old = load(os.path.join(BAK, stem + '.json'))
    new = load(os.path.join(OUT, stem + '.json'))
    if old is None or new is None:
        continue
    for key in ('balance', 'income_statement', 'cash_flow'):
        o, n = items_map(old, key), items_map(new, key)
        if not o and not n:
            continue
        tot_old += len(o); tot_new += len(n)
        for k in set(o) | set(n):
            if k not in o:
                gained += 1
            elif k not in n:
                lost += 1
            elif o[k] != n[k]:
                changed += 1
            else:
                same += 1
        if has_terminal(old, key) and not has_terminal(new, key):
            term_regress.append('%s / %s' % (stem, key))

print('=== значения строк (код × колонка)')
print('  совпало:        %d' % same)
print('  появилось:      %d' % gained)
print('  пропало:        %d' % lost)
print('  изменилось:     %d' % changed)
print('  всего ячеек: было %d, стало %d' % (tot_old, tot_new))
print()

print('=== полнота формы (замыкающий код)')
if term_regress:
    print('  ПОТЕРЯЛИ замыкающий код: %d случаев' % len(term_regress))
    for s in term_regress[:12]:
        print('     %s' % s)
else:
    print('  ни один документ не потерял замыкающий код — это главное')
print()

old_term = new_term = 0
for stem in stems:
    old = load(os.path.join(BAK, stem + '.json'))
    new = load(os.path.join(OUT, stem + '.json'))
    if old is None or new is None:
        continue
    for key in ('balance', 'income_statement', 'cash_flow'):
        if items_map(old, key) and has_terminal(old, key):
            old_term += 1
        if items_map(new, key) and has_terminal(new, key):
            new_term += 1
print('  форм с замыкающим кодом: было %d, стало %d' % (old_term, new_term))
