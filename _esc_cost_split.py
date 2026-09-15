# -*- coding: utf-8 -*-
r"""Из чего состоит цена эскалации: транскрипция страниц против структурирования.

ВАЖНО: в `_pv_usage.json` поле `cost` посчитано неверно (одна и та же сумма поделена
и на входные, и на выходные токены), а токены верны. Проверка: 84 вызова эскалации,
401575 входных и 162299 выходных токенов по ценам PlusVibe 49.03/245.15 дают
19.69 + 39.79 = 59.48 ₽ — ровно измеренную ранее цену роли. То же для main
(923532 × 3.78 + 2812801 × 18.86 = 3.49 + 53.05 = 56.54 ₽) и detect (0.22 ₽).
Сумма трёх ролей 116.24 ₽ = измеренная цена пилота 116.23 ₽.
"""
import io, json, hashlib, sys

sys.path.insert(0, r'D:\models')
import providers as PR

pv = PR.active('plusvibe')
roles = {}
for role in ('detect', 'main', 'esc'):
    m = pv.roles.get(role)
    if m:
        roles[hashlib.sha1(m.encode()).hexdigest()[:10]] = role

d = json.load(io.open(r'D:\models\_pv_usage.json', encoding='utf-8'))

print('=== цена по ролям, посчитанная по ВЕРНЫМ ценам ===')
real = {}
for e in d:
    role = roles.get((e.get('sha1') or '')[:10], '?')
    model = pv.roles.get(role)
    pin, pout = pv.price_of(model) if model else (0, 0)
    pt, ct = e.get('pt') or 0, e.get('ct') or 0
    cost = pt / 1e6 * pin + ct / 1e6 * pout
    real[role] = {'calls': e.get('calls') or 0, 'pt': pt, 'ct': ct, 'cost': cost,
                  'pin': pin, 'pout': pout}
    print('  %-7s вызовов %4d, вход %8d, выход %8d -> %6.2f ₽  (%.2f/%.2f за 1М)'
          % (role, e.get('calls') or 0, pt, ct, cost, pin, pout))
tot = sum(v['cost'] for v in real.values())
print('  ИТОГО %.2f ₽  (измеренная цена пилота 116.23 ₽)' % tot)
print()

e = real.get('esc') or {}
c = e.get('cost') or 0
PAGES = 43          # страниц 300 dpi в подтверждённых случаях (из _esc_payoff3.py)
PAGE_COST = 4781 / 1e6 * e.get('pin', 0) + 1932 / 1e6 * e.get('pout', 0)
tr = PAGES * PAGE_COST
print('=== эскалация %.2f ₽: транскрипция против структурирования ===' % c)
print('  страница 300 dpi стоит %.3f ₽ (4781 вход + 1932 выход)' % PAGE_COST)
print('  транскрипция %d стр.:        %6.2f ₽ (%.0f%%)' % (PAGES, tr, 100 * tr / c))
print('  структурирование:            %6.2f ₽ (%.0f%%)' % (c - tr, 100 * (c - tr) / c))
print()
print('=== сколько эскалации не дало ни одного исправления ===')
print('  случаев всего 9; исправили строки 2 (6 стр.); не исправили 7 (37 стр.)')
n_nouse_pages = 37
tr_no = n_nouse_pages * PAGE_COST
st_no = (c - tr) / 9 * 7
print('  транскрипция 37 стр.: %6.2f ₽' % tr_no)
print('  структурирование 7 вызовов: %6.2f ₽' % st_no)
print('  итого впустую:        %6.2f ₽ (%.0f%% всей эскалации)'
      % (tr_no + st_no, 100 * (tr_no + st_no) / c))
print()
print('  из них наш собственный дефект (правило 1200 без 1215), КЛВЗ оба года:')
k = 16 * PAGE_COST + (c - tr) / 9 * 2
print('    16 стр. + 2 структурирования = %6.2f ₽' % k)
print('  остальное — документы, которые действительно не сходятся (второе мнение):')
print('    %6.2f ₽' % (tr_no + st_no - k))
