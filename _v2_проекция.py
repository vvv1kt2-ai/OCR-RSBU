# -*- coding: utf-8 -*-
r"""Проекция на корпус: сравнение с базой и поправка на текстовый слой.

Сравнивать «62.65 ₽ против 116.23 ₽» можно, но этого мало: пилот — 41 документ из 173, и
если в пилоте доля документов с текстовым слоем выше, чем в корпусе, проекция будет
оптимистичной. У документов с текстовым слоем LLM только структурирует (1-4 вызова), у
сканов она ещё и читает страницы — разница в цене разы.

Поэтому считаем не «средняя цена × масштаб», а отдельно по двум классам: сколько стоил
документ с текстовым слоем и сколько — скан, затем применяем доли из замера корпуса
(1222 страницы с текстовым слоем из 5884; документов без слоя совсем — 130 из 173).
"""
import io, json, os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
NEW = json.load(io.open(r'D:\models\_v2_прогон.json', encoding='utf-8'))
cost = {r['stem']: r for r in NEW['rows']}

rows = []
for fn in sorted(os.listdir(OUT)):
    if not fn.endswith('.json') or fn.startswith('_'):
        continue
    stem = os.path.splitext(fn)[0]
    try:
        r = json.load(io.open(os.path.join(OUT, fn), encoding='utf-8'))
    except Exception:
        continue
    c = cost.get(stem)
    tl = bool(r.get('source', {}).get('text_layer'))
    pages = 0
    for k in ('balance', 'income_statement', 'cash_flow'):
        d = r.get(k)
        if d:
            pages += len(d.get('items') or [])
    rows.append((stem, tl, r.get('status'), c['cost'] if c else 0.0,
                 c['calls'] if c else 0, c['pages'] if c else 0))

print('документов: %d' % len(rows))
tot = sum(r[3] for r in rows)
print('ПОТРАЧЕНО НА ПИЛОТ: %.2f ₽ (в строке ИТОГО прогона было 62.65 ₽)' % tot)
print()

for tl in (True, False):
    sub = [r for r in rows if r[1] is tl]
    if not sub:
        continue
    cs = sum(r[3] for r in sub)
    ps = sum(r[5] for r in sub)
    print('%-22s документов %2d, цена %6.2f ₽, страниц прочитано %3d, '
          'средняя %5.2f ₽/док, %5.3f ₽/стр'
          % ('с текстовым слоем:' if tl else 'сканы (LLM читает):',
             len(sub), cs, ps, cs / len(sub), cs / max(ps, 1)))
print()

tl_docs = [r for r in rows if r[1]]
sc_docs = [r for r in rows if not r[1]]
tl_cost = sum(r[3] for r in tl_docs) / max(len(tl_docs), 1)
sc_cost = sum(r[3] for r in sc_docs) / max(len(sc_docs), 1)

# доли в корпусе: страниц с текстовым слоем 1222 из 5884 (20.8%), документов без слоя 130
CORPUS_DOCS = 173
CORPUS_PAGES = 5884
CORPUS_TEXT_SHARE = 1222 / 5884
print('доля пилота по классам: с текстовым слоем %d из %d (%.0f%%), сканы %d'
      % (len(tl_docs), len(rows), 100.0 * len(tl_docs) / len(rows), len(sc_docs)))
print('в корпусе доля страниц с текстовым слоем: %.0f%%' % (100 * CORPUS_TEXT_SHARE))
print()

print('=== сравнение с базой (цены plusvibe)')
base = 116.23
print('  было (пилот, цены plusvibe): %.2f ₽' % base)
print('  стало (пилот, измерено):     %.2f ₽' % tot)
print('  изменение: %+.2f ₽ (%+.0f%%)' % (tot - base, 100.0 * (tot - base) / base))
print()
print('=== проекция на корпус')
print('  по документам (173/41 = %.2f): %.0f ₽' % (CORPUS_DOCS / 41, tot * CORPUS_DOCS / 41))
print('  по страницам (5884/1263 = %.2f): %.0f ₽' % (CORPUS_PAGES / 1263, tot * CORPUS_PAGES / 1263))
print()
print('  осторожная оценка по классам: пилотные средние %.2f ₽ (текст) и %.2f ₽ (скан);'
      % (tl_cost, sc_cost))
print('  в корпусе 130 сканов из 173, остальные 43 с текстовым слоем:')
proj = 130 * sc_cost + 43 * tl_cost
print('     130 × %.2f + 43 × %.2f = %.0f ₽' % (sc_cost, tl_cost, proj))
print()
print('  (пилот: сканов %d из %d — если их доля ниже корпусной, проекция по масштабу занижена)'
      % (len(sc_docs), len(rows)))
print()
print('=== статусы')
import collections
print('  %s' % dict(collections.Counter(r[2] for r in rows)))
