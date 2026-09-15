# -*- coding: utf-8 -*-
r"""Оправдалась ли эскалация ОФР/ОДДС: что сказано в warnings и проходят ли проверки.

Эскалация не-баланса возможна только в скан-ветке (pipeline.py:1049) и раньше
считалась бесплатной мелочью. Проверяю, принесла ли она пользу.
"""
import io, os, json, re

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

targets = {}
for f in os.listdir(PAGES):
    m = re.search(r'_(esc)_(balance|income_statement|cash_flow)', f)
    if m and m.group(2) != 'balance':
        stem = re.sub(r'\.pdf_esc_.*$', '', f)
        stem = re.sub(r'^_llm_', '', stem)
        targets.setdefault(stem, set()).add(m.group(2))

print('документов с эскалацией ОФР/ОДДС: %d' % len(targets))
for stem, forms in sorted(targets.items()):
    doc = json.load(io.open(os.path.join(EX, stem + '.json'), encoding='utf-8'))
    src = doc.get('source') or {}
    print()
    print('%s  (форм: %s, текстовый слой: %s, страниц %s)'
          % (stem, ','.join(sorted(forms)), src.get('text_layer'), src.get('pages_total')))
    for w in (doc.get('warnings') or []):
        if re.search(r'эскалац|escalat|fixed|reconcil', w, re.I):
            print('    warning: %s' % w[:150])
    for c in (doc.get('checks') or []):
        if c['form'] in forms:
            print('    проверка %-17s %-46s -> %s'
                  % (c['form'], c['rule'][:46], 'пройдена' if c.get('ok') else 'ПРОВАЛ'))
    for fm in sorted(forms):
        d = doc.get(fm) or {}
        items = d.get('items') or []
        corrected = [it for it in items if it.get('corrected_by')]
        confirmed = [it for it in items if it.get('confirmed_by')]
        print('    %s: строк %d, исправлено эскалацией %d, подтверждено %d'
              % (fm, len(items), len(corrected), len(confirmed)))
