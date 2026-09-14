# -*- coding: utf-8 -*-
r"""Пересчёт через производственную проверку: сколько провалов даёт неполное правило 1200.

Прошлый замер сравнивал числа точно, а конвейер сравнивает с допуском 2 (`TOL = 2`,
`pipeline.py:384`), и правило считается пройденным, только если НИ ОДНА колонка не
провалилась (`ok = all(v is not False ...)`, строка 429). Поэтому проверять надо
производственной функцией, а не своей арифметикой.

«Починенное» правило моделируется добавлением к строке 1210 значения строки 1215:
тогда сумма в правиле включает 1215, а остальные строки не меняются.
"""
import io, os, copy, json, sys

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

pv = PR.active('plusvibe')
E_IN, E_OUT = pv.price_of(pv.roles['esc'])
ESC_PAGE = 4781 / 1e6 * E_IN + 1932 / 1e6 * E_OUT

RULE = '1200 == 1210+1220+1230+1240+1250+1260'


def merge_1215(items):
    """Копия items, где в 1210 добавлено 1215 — модель правила, знающего 1215."""
    out = copy.deepcopy(items)
    v1215 = None
    for it in out:
        if str(it.get('code') or '') == '1215':
            v1215 = it.get('values') or []
    if not v1215:
        return None
    for it in out:
        if str(it.get('code') or '') == '1210':
            v = list(it.get('values') or [])
            for i in range(max(len(v), len(v1215))):
                a = v[i] if i < len(v) else None
                b = v1215[i] if i < len(v1215) else None
                if b is None:
                    continue
                v = v + [None] * (i + 1 - len(v))
                v[i] = (a or 0) + b
            it['values'] = v
            return out
    return None


def rule_ok(checks, rule=RULE):
    for c in checks:
        if c.get('rule') == rule:
            return c.get('ok')
    return None


print('=== провал правила 1200: как есть и с учётом 1215 ===')
print('%-30s %-12s %-12s %-8s %s' % ('документ', 'как есть', 'с 1215', 'эскал.', 'колонки'))
print('-' * 84)
rows = []
for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    bal = doc.get('balance') or {}
    items = bal.get('items') or []
    if not items:
        continue
    if not any(str(it.get('code') or '') == '1215' and any(
            v not in (None, '', '-') for v in (it.get('values') or [])) for it in items):
        continue
    now = P.run_checks('balance', items)
    fixed_items = merge_1215(items)
    fixed = P.run_checks('balance', fixed_items) if fixed_items else None
    a = rule_ok(now)
    b = rule_ok(fixed) if fixed else None
    pages = [p for p in (bal.get('transcript_pages') or []) if isinstance(p, int)]
    esc = [f for f in os.listdir(PAGES)
           if f.startswith('_llm_%s.pdf_esc_balance' % stem)]
    esc_pages = min(len(pages), 8) if esc else 0
    pc = [c['per_column'] for c in now if c['rule'] == RULE][0]
    rows.append((stem, a, b, bool(esc), esc_pages, pc))
    print('%-30s %-12s %-12s %-8s %s'
          % (stem[:30], 'прошла' if a else 'ПРОВАЛ', 'прошла' if b else 'ПРОВАЛ',
             'да' if esc else 'нет', pc))
print('-' * 84)
print()
n_now = sum(1 for r in rows if not r[1])
n_fixed = sum(1 for r in rows if not r[2])
print('документов с кодом 1215: %d' % len(rows))
print('провал правила 1200 как есть: %d' % n_now)
print('провал правила 1200 с учётом 1215: %d' % n_fixed)
print()
print('=== цена вопроса ===')
print('эскалация запускается при любом провале проверки формы (pipeline.py:1050),')
print('то есть неполное правило тратит деньги:')
tot = 0
for stem, a, b, esc, ep, pc in rows:
    if a is False and b is True:
        tot += ep
        print('  %-30s провал снят правилом, эскалация %d стр. = %.2f ₽'
              % (stem[:30], ep, ep * ESC_PAGE))
print('  всего страниц: %d, стоимость %.2f ₽ (пилот)' % (tot, tot * ESC_PAGE))
print()
print('но эскалация могла сработать и из-за других провалов; проверяю:')
for stem, a, b, esc, ep, pc in rows:
    doc = json.load(io.open(os.path.join(EX, stem + '.json'), encoding='utf-8'))
    bad = [(c['form'], c['rule']) for c in (doc.get('checks') or []) if not c.get('ok')]
    print('  %-30s провалов всего %d: %s' % (stem[:30], len(bad), bad[:3]))
json.dump([{'stem': r[0], 'now': r[1], 'with1215': r[2], 'esc': r[3], 'pages': r[4],
            'per_column': r[5]} for r in rows],
          io.open(r'D:\models\_check_rules2.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
