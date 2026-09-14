# -*- coding: utf-8 -*-
"""Разбор стоимости: сколько съедает эскалация и сколько вывода — рассуждения.

Два вопроса, на которые в логах нет прямого ответа:
  1. какую долю стоимости даёт эскалация (по числу вызовов и по цене);
  2. сколько выходных токенов уходит на сам транскрипт, а сколько — на рассуждения
     модели. Токены рассуждений поставщик считает выходными и не показывает отдельно,
     поэтому оцениваем косвенно: сравниваем длину готового текста с числом выходных
     токенов. Русский текст в современных разметчиках — примерно 2–3 знака на токен,
     значит транскрипт в 4000 знаков стоит около 1300–2000 токенов. Всё, что сверх
     этого, — рассуждения.
"""
import io, os, json

Q = json.load(io.open(r'D:\models\_pv_quality.json', encoding='utf-8'))
U = json.load(io.open(r'D:\models\_pv_usage.json', encoding='utf-8'))
UROWS = U['rows'] if isinstance(U, dict) else U
CACHE = r'D:\models\extracted\pages\_pvq'

# --- 1. доля эскалации ------------------------------------------------------
PV = {  # цены PlusVibe по ролям, RUB за 1М токенов (из providers.json)
    'main': (3.78, 18.86),
    'esc': (49.03, 245.15),
    'detect': (0.76, 3.02),
}
ROLE = {}   # len/sha1 -> роль
import sys
sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR
import hashlib


def idof(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


pv = PR.active('plusvibe')
for role in ('main', 'esc', 'detect'):
    ROLE[idof(pv.roles[role])] = role
for role in ('main', 'esc', 'detect'):     # роли Polza: detect там другая модель
    ROLE.setdefault(idof(P.ACTIVE_PROFILE.roles[role]), role)

print('=== стоимость по ролям (наш прогон 20 документов) ===')
print('%-8s %6s %10s %10s %10s %10s' % ('роль', 'вызовов', 'вход тк', 'выход тк',
                                         'Polza ₽', 'PlusVibe ₽'))
tot = {'p': 0.0, 'v': 0.0}
agg = {}
for r in UROWS:
    role = ROLE.get(r['sha1'], '?')
    a = agg.setdefault(role, {'calls': 0, 'pt': 0, 'ct': 0, 'p': 0.0, 'v': 0.0})
    a['calls'] += r['calls']; a['pt'] += r['pt']; a['ct'] += r['ct']
    a['p'] += r['cost']
    pin, pout = PV.get(role, (0, 0))
    a['v'] += r['pt'] / 1e6 * pin + r['ct'] / 1e6 * pout
for role in sorted(agg, key=lambda k: -agg[k]['v']):
    a = agg[role]
    tot['p'] += a['p']; tot['v'] += a['v']
    print('%-8s %6d %10d %10d %10.2f %10.2f' % (role, a['calls'], a['pt'], a['ct'],
                                                a['p'], a['v']))
print('%-8s %6s %10s %10s %10.2f %10.2f' % ('ИТОГО', '', '', '', tot['p'], tot['v']))
print()
for role in sorted(agg, key=lambda k: -agg[k]['v']):
    print('  доля %-7s в цене PlusVibe: %5.1f%%   в цене Polza: %5.1f%%'
          % (role, 100 * agg[role]['v'] / tot['v'], 100 * agg[role]['p'] / tot['p']))

# --- 2. вывод: транскрипт или рассуждения -----------------------------------
print()
print('=== выходные токены против длины готового текста (20 страниц PlusVibe) ===')
ct = sum(r['ct'] for r in Q['rows'])
chars = sum(len(io.open(os.path.join(CACHE, r['pv_file']), encoding='utf-8').read())
            for r in Q['rows'])
print('страниц: %d, выходных токенов: %d, знаков в ответах: %d' % (len(Q['rows']), ct, chars))
print('знаков на выходной токен: %.2f' % (chars / ct))
print()
print('Если бы весь выход был транскриптом, знаков на токен было бы 2–3.')
print('Оценка доли рассуждений в выходных токенах:')
for cpt in (2.0, 2.5, 3.0):
    need = chars / cpt
    print('  при %.1f знака на токен: транскрипт ≈ %d тк, рассуждения ≈ %d тк (%.0f%%)'
          % (cpt, need, ct - need, 100 * (ct - need) / ct))

# --- 3. сколько документов эскалировалось -----------------------------------
print()
PAGES = r'D:\models\extracted\pages'
esc = [f for f in os.listdir(PAGES) if '_esc_' in f and f.endswith('.json')
       and '_quarantine' not in f]
docs = sorted({f.split('_esc_')[0] for f in esc})
res = [f for f in os.listdir(r'D:\models\extracted') if f.endswith('.json')
       and not f.startswith('_')]
print('=== эскалация ===')
print('документов с результатом: %d' % len(res))
print('документов, где эскалация сработала: %d' % len(docs))
for d in docs:
    print('   ', d)
