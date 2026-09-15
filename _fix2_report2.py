# -*- coding: utf-8 -*-
r"""Пересчёт правки 2 С УЧЁТОМ области форм.

Первая версия разбора считала все три формы для всех документов и потому преувеличила
и потери, и рост цены: `wanted_forms()` для файлов `_2025` оставляет ТОЛЬКО баланс
(сокращение области), так что исчезновение ОФР и ОДДС в файле за 2025 год потерей не
является. Здесь сравниваю только те формы, которые конвейер действительно читает.
"""
import io, os, re, sys, json

sys.path.insert(0, r'D:\models')
import pipeline as P

PAGES = P.PAGESDIR


def labels(path):
    pm = json.load(io.open(path, encoding='utf-8'))
    return {p['page']: p.get('form') for p in pm
            if isinstance(p, dict) and isinstance(p.get('page'), int)}


rows = []
for f in sorted(os.listdir(PAGES)):
    m = re.match(r'^_llm_(.+)_detect_v2\.json$', f)
    if not m:
        continue
    stem = m.group(1)
    name = stem + '.pdf'
    old_p = os.path.join(PAGES, f'_llm_{stem}_detect.json')
    new_p = os.path.join(PAGES, f)
    if not os.path.exists(old_p):
        continue
    old, new = labels(old_p), labels(new_p)
    want = P.wanted_forms(name) or set(P.FORM_LABELS)
    o = {k: sum(1 for v in old.values() if v == k) for k in want}
    n = {k: sum(1 for v in new.values() if v == k) for k in want}
    rows.append((stem, sorted(want), sum(o.values()), sum(n.values()), o, n,
                 sorted(p for p, v in new.items() if v in ('notes', 'audit'))))

print('документов: %d' % len(rows))
print()
o_tot = sum(r[2] for r in rows)
n_tot = sum(r[3] for r in rows)
print('=== ЦЕНА: страниц нужных форм читалось -> будет читаться ===')
print('   всего: %d -> %d  (%+d страниц, %+.0f%%)'
      % (o_tot, n_tot, n_tot - o_tot,
         100.0 * (n_tot - o_tot) / o_tot if o_tot else 0))
print()
print('   стало больше:')
for r in sorted(rows, key=lambda r: -(r[3] - r[2]))[:10]:
    if r[3] > r[2]:
        print('      %-34s область=%-22s %d -> %d (%+d)'
              % (r[0][:34], ','.join(r[1]), r[2], r[3], r[3] - r[2]))
print('   стало меньше:')
for r in sorted(rows, key=lambda r: (r[3] - r[2]))[:10]:
    if r[3] < r[2]:
        print('      %-34s область=%-22s %d -> %d (%+d)'
              % (r[0][:34], ','.join(r[1]), r[2], r[3], r[3] - r[2]))
print()

print('=== НУЖНАЯ ФОРМА ОСТАЛАСЬ БЕЗ СТРАНИЦ (вот это потеря) ===')
n0 = 0
for r in rows:
    for k in r[1]:
        if r[5].get(k, 0) == 0:
            n0 += 1
            print('   %-34s форма %-17s было страниц: %d' % (r[0][:34], k, r[4].get(k, 0)))
if not n0:
    print('   нет ни одного случая')
print()

print('=== ЧТО ТЕПЕРЬ НЕ ЧИТАЕТСЯ (notes/audit) ===')
tot = sum(len(r[6]) for r in rows)
print('   страниц: %d в %d документах' % (tot, sum(1 for r in rows if r[6])))
print()
print('=== ПО ДОКУМЕНТАМ, ГДЕ ОБЛАСТЬ — ВСЕ ТРИ ФОРМЫ ===')
for r in rows:
    if len(r[1]) == 3:
        print('   %-34s было %d -> стало %d  %s' % (r[0][:34], r[2], r[3], r[5]))
