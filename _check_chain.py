# -*- coding: utf-8 -*-
r"""Цепочка: неполное правило → ложный провал → лишняя эскалация → деньги.

Проверяются те 4 документа, где есть строка 1215, которой нет в правиле:
провалилась ли у них проверка 1200 и запустилась ли из-за этого эскалация.
Арифметика считается по самим данным: сходится ли 1200 с суммой, если добавить 1215.
"""
import io, os, re, json, sys

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

TARGETS = ['КЛВЗ Кристалл_6мес_2025', 'КЛВЗ Кристалл_6мес_2026',
           'ТГК-14_6мес_2025', 'ТГК-14_6мес_2026']
RULE_CODES = ['1210', '1220', '1230', '1240', '1250', '1260']
pv = PR.active('plusvibe')
E_IN, E_OUT = pv.price_of(pv.roles['esc'])
ESC_PAGE = 4781 / 1e6 * E_IN + 1932 / 1e6 * E_OUT

print('=== сходится ли сумма с учётом 1215 ===')
print('%-30s %-6s %12s %12s %12s %10s'
      % ('документ', 'стр.', 'сумма', 'по правилу', '1200', 'с 1215'))
print('-' * 92)
total_esc_pages = 0
for stem in TARGETS:
    p = os.path.join(EX, stem + '.json')
    if not os.path.exists(p):
        continue
    doc = json.load(io.open(p, encoding='utf-8'))
    bal = doc.get('balance') or {}
    by = {}
    for it in (bal.get('items') or []):
        c = str(it.get('code') or '').strip()
        if c:
            by[c] = it.get('values') or []
    cols = bal.get('columns') or []
    # сколько страниц ушло на эскалацию
    esc = [f for f in os.listdir(PAGES)
           if f.startswith('_llm_%s.pdf_esc_balance' % stem)]
    pages = [p for p in (bal.get('transcript_pages') or []) if isinstance(p, int)]
    esc_pages = min(len(pages), 8) if esc else 0
    total_esc_pages += esc_pages

    def num(c, i):
        v = by.get(c) or []
        v = v[i] if i < len(v) else None
        if v in (None, '', '-', '—'):
            return 0
        try:
            return int(str(v).replace(' ', '').replace('\u00a0', ''))
        except ValueError:
            return None

    for i in range(min(3, len(cols))):
        rule_sum = sum(x for x in (num(c, i) for c in RULE_CODES) if x)
        with1215 = rule_sum + (num('1215', i) or 0)
        v1200 = num('1200', i)
        ok_rule = 'сход.' if v1200 == rule_sum else 'НЕ сход.'
        ok_1215 = 'сход.' if v1200 == with1215 else 'НЕ сход.'
        print('%-30s %-6d %12d %12s %12s %10s'
              % (stem[:30], i + 1, with1215, ok_rule, v1200, ok_1215))
    print('%-30s эскалация: %s, страниц в ней: %d'
          % ('', 'да' if esc else 'нет', esc_pages))

print('-' * 92)
print()
print('=== проверка 1200 в итоговом результате ===')
for stem in TARGETS:
    p = os.path.join(EX, stem + '.json')
    if not os.path.exists(p):
        continue
    doc = json.load(io.open(p, encoding='utf-8'))
    for c in (doc.get('checks') or []):
        if c.get('form') == 'balance' and '1200' in str(c.get('rule') or ''):
            print('  %-30s %-6s %s' % (stem[:30], 'прошла' if c.get('ok') else 'ПРОВАЛ',
                                       c.get('rule')))
print()
print('страниц эскалации по этим 4 документам: %d, цена %.2f ₽' % (total_esc_pages,
                                                                   total_esc_pages * ESC_PAGE))
print('(часть из них вызвана, возможно, и другими провалами — не только 1215)')
