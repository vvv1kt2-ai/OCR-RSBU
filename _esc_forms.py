# -*- coding: utf-8 -*-
r"""Куда уходят деньги эскалации: баланс или ОФР/ОДДС.

В скан-ветке эскалация вызывается для ВСЕХ трёх форм (`pipeline.py:1049`), а в
текстовой — только для баланса (`pipeline.py:1168`). Значит провал проверки ОФР или
ОДДС в скане стоит денег. Проверяю по кэшу эскалации, без вызовов LLM.
"""
import io, os, json, re, sys

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

esc = {}
for f in os.listdir(PAGES):
    m = re.search(r'_esc_(balance|income_statement|cash_flow)', f)
    if m:
        stem = re.sub(r'\.pdf_esc_.*$', '', f)
        esc.setdefault(stem, set()).add(m.group(1))

print('=== формы, которые эскалировались (по кэшу страниц 300 dpi) ===')
by_form = {}
for stem, forms in sorted(esc.items()):
    for fm in forms:
        by_form.setdefault(fm, []).append(stem)
for fm, stems in sorted(by_form.items()):
    print('  %-18s документов %d' % (fm, len(stems)))

print()
print('=== почему провалилась каждая форма: какие правила ===')
rows = []
for stem, forms in sorted(esc.items()):
    path = os.path.join(EX, stem + '.json')
    if not os.path.exists(path):
        continue
    doc = json.load(io.open(path, encoding='utf-8'))
    src = doc.get('source') or {}
    scan = not src.get('text_layer')
    for c in (doc.get('checks') or []):
        if c.get('ok'):
            continue
        if c['form'] in forms:
            rows.append((stem, c['form'], c['rule'], scan))

for stem, fm, rule, scan in rows:
    print('  %-28s %-17s %-46s %s' % (stem[:28], fm, rule[:46], 'скан' if scan else 'текст'))

print()
print('=== итог ===')
n_bal = sum(1 for r in rows if r[1] == 'balance')
n_other = sum(1 for r in rows if r[1] != 'balance')
print('провалов, вызвавших эскалацию: баланс %d, ОФР/ОДДС %d' % (n_bal, n_other))
print('документов с эскалацией не-баланса: %d'
      % len({r[0] for r in rows if r[1] != 'balance'}))
ESC_PAGE = 0.708
print()
print('страниц 300 dpi в кэше всего: %d' % sum(len(v) for v in esc.values()))
print('из них относятся к ОФР/ОДДС: %d'
      % sum(len([f for f in os.listdir(PAGES) if '_esc_%s' % fm in f])
            for fm in ('income_statement', 'cash_flow')))
json.dump([{'stem': r[0], 'form': r[1], 'rule': r[2], 'scan': r[3]} for r in rows],
          io.open(r'D:\models\_esc_forms.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
