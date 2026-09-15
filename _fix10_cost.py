# -*- coding: utf-8 -*-
r"""Цена вызовов по ролям: сколько стоит детекция одной страницы и транскрипция.

Читает журнал расходов поставщика (`_pv_usage.json`) и печатает только сводку: по каждой
модели — число вызовов, средние токены и средняя цена вызова. Никаких сырых записей.
"""
import io, json, os, sys, collections

sys.path.insert(0, r'D:\models')
import pipeline as P

PATH = r'D:\models\_pv_usage.json'
raw = json.load(io.open(PATH, encoding='utf-8'))
recs = raw if isinstance(raw, list) else raw.get('records', [])
print('записей в журнале расходов: %d' % len(recs))
print()

PRICES = P.PRICES
by = collections.defaultdict(lambda: {'n': 0, 'pt': 0, 'ct': 0, 'rub': 0.0})
for r in recs:
    if not isinstance(r, dict):
        continue
    m = r.get('model') or r.get('model_name') or '?'
    pt = r.get('prompt_tokens') or r.get('pt') or 0
    ct = r.get('completion_tokens') or r.get('ct') or 0
    rub = r.get('cost_rub')
    if rub is None:
        pr = PRICES.get(m)
        rub = (pt * pr[0] + ct * pr[1]) / 1e6 if pr else 0.0
    d = by[m]
    d['n'] += 1; d['pt'] += pt; d['ct'] += ct; d['rub'] += rub

print('%-26s %6s %10s %10s %12s %14s'
      % ('модель', 'вызовов', 'вход/выз', 'выход/выз', 'всего ₽', 'за вызов ₽'))
for m, d in sorted(by.items(), key=lambda kv: -kv[1]['n']):
    print('%-26s %6d %10.0f %10.0f %12.3f %14.5f'
          % (m[:26], d['n'], d['pt'] / d['n'], d['ct'] / d['n'], d['rub'], d['rub'] / d['n']))

print()
detect_model = P.ACTIVE_PROFILE.roles['detect']
main_model = P.ACTIVE_PROFILE.roles['main']
print('роль detect сейчас: %s' % detect_model)
print('роль main сейчас:   %s' % main_model)
print()
for role, model in (('detect', detect_model), ('main', main_model)):
    d = by.get(model)
    if not d:
        print('роль %s: записей по модели нет' % role); continue
    print('роль %s: %.5f ₽ за вызов (по %d вызовам)' % (role, d['rub'] / d['n'], d['n']))
print()
# проекция на корпус
corpus_pages = 5884
dd = by.get(detect_model)
if dd:
    per = dd['rub'] / dd['n']
    print('ПРОЕКЦИЯ на корпус %d страниц:' % corpus_pages)
    print('  постраничная детекция (1 вызов на страницу): %.1f ₽' % (per * corpus_pages))
    print('  группами по 8 (%.0f вызовов):               %.1f ₽'
          % (corpus_pages / 8, per * corpus_pages / 8 * 1.0))
    print('  (вторая строка — оценка снизу: в групповом вызове входных токенов больше)')
