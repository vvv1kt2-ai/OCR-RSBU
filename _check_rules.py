# -*- coding: utf-8 -*-
r"""Ложные провалы проверок: правила не знают части кодов действующего плана счетов.

Правило `1200 == 1210+1220+1230+1240+1250+1260` не включает 1215 (Долгосрочные активы
к продаже), а `1100 == 1110+1150+1160+1170+1180+1190` не включает 1105, 1120, 1130,
1140. Если организация показывает эти строки, проверка падает на верном извлечении —
а провал проверки запускает эскалацию, то есть тратит деньги.

Здесь считается, как часто такие строки вообще встречаются в извлечённых данных.
"""
import io, os, json, sys
from collections import Counter

sys.path.insert(0, r'D:\models')

EX = r'D:\models\extracted'
res_files = sorted(f for f in os.listdir(EX)
                   if f.endswith('.json') and not f.startswith('_'))

OMITTED = {
    '1100': ['1105', '1120', '1130', '1140'],
    '1200': ['1215'],
}
present = Counter()
docs_with = Counter()
total_forms = 0
rows_with = {}

for rf in res_files:
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    bal = doc.get('balance') or {}
    items = bal.get('items') or []
    if not items:
        continue
    total_forms += 1
    by_code = {}
    for it in items:
        c = str(it.get('code') or '').strip()
        if not c:
            continue
        vals = it.get('values') or []
        filled = [v for v in vals if v not in (None, '', '-')]
        if filled:
            by_code[c] = filled
    for parent, codes in OMITTED.items():
        hit = [c for c in codes if c in by_code]
        if hit:
            docs_with[parent] += 1
            for c in hit:
                present[c] += 1
            rows_with.setdefault(parent, []).append((stem, hit, by_code.get(parent)))

print('=== есть ли в данных строки, которых нет в правилах проверок ===')
print('балансов разобрано: %d' % total_forms)
print()
print('%-8s %-28s %10s %10s' % ('правило', 'коды вне правила', 'строк', 'документов'))
print('-' * 60)
for parent, codes in OMITTED.items():
    for c in codes:
        print('%-8s %-28s %10d %10s'
              % (parent, c, present[c], docs_with[parent] if present[c] else 0))
print('-' * 60)
print()
print('документов, где правило неполно:')
for parent in OMITTED:
    print('  %-6s %d из %d балансов' % (parent, docs_with[parent], total_forms))
print()
print('=== подробности ===')
for parent, lst in rows_with.items():
    for stem, hit, parent_val in lst[:15]:
        print('  %-34s правило %s: есть коды %s, само %s = %s'
              % (stem[:34], parent, hit, parent, parent_val))

json.dump({'total_forms': total_forms,
           'docs_with': dict(docs_with),
           'codes': dict(present),
           'details': {k: v[:40] for k, v in rows_with.items()}},
          io.open(r'D:\models\_check_rules.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print()
print('-> _check_rules.json')
