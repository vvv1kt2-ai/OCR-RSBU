# -*- coding: utf-8 -*-
r"""Готовность к проверке эскалации: где есть и кэш Polza 300 dpi, и текстовый слой.

Эскалация — самая дорогая часть (51% цены), и судить её можно только там, где
известна истина. Истина бесплатна там, где у страницы есть текстовый слой PDF.
"""
import io, os, re, json, sys, hashlib

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR
import fitz

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
DL = r'D:\data-scraping\downloads'
ESC_TAG = P.model_tag(P.M_ESC)
print('метка модели эскалации у Polza: len=%d sha1=%s'
      % (len(ESC_TAG), hashlib.sha1(ESC_TAG.encode()).hexdigest()[:8]))

survey = json.load(io.open(r'D:\models\_escdet_survey.json', encoding='utf-8'))
pat = re.compile(r'^(.+)_p(\d+)_300_(.+?)(?:_pv)?_([0-9a-f]{10})\.md$')

print()
print('=== страницы эскалации: есть ли кэш Polza и текстовый слой ===')
print('%-32s %-9s %4s %10s %10s %12s'
      % ('документ', 'форма', 'стр', 'кэш Polza', 'слой знаков', 'слой годится'))
print('-' * 86)
tot = {'pages': 0, 'cache': 0, 'usable': 0, 'cost': 0.0}
pv = PR.active('plusvibe')
E_IN, E_OUT = pv.price_of(pv.roles['esc'])
PAGE_COST = 4781 / 1e6 * E_IN + 1932 / 1e6 * E_OUT

targets = []
for r in survey:
    stem = r['stem']
    pdf = os.path.join(DL, stem + '.pdf')
    if not os.path.exists(pdf):
        continue
    d = fitz.open(pdf)
    for p in r['pages']:
        files = []
        for fn in os.listdir(PAGES):
            m = pat.match(fn)
            if m and m.group(1) == stem and int(m.group(2)) == p and m.group(3) == ESC_TAG:
                files.append(fn)
        layer = d[p - 1].get_text() if 1 <= p <= d.page_count else ''
        ok = len(layer) > 200
        tot['pages'] += 1
        tot['cache'] += 1 if files else 0
        tot['usable'] += 1 if ok else 0
        if ok:
            tot['cost'] += PAGE_COST
            targets.append({'stem': stem, 'form': r['forms'][0], 'page': p,
                            'files': files, 'layer_len': len(layer)})
        print('%-32s %-9s %4d %10s %10d %12s'
              % (stem[:32], ','.join(r['forms'])[:9], p,
                 'да' if files else 'НЕТ', len(layer), 'да' if ok else 'нет'))
    d.close()

print('-' * 86)
print('страниц эскалации всего: %d' % tot['pages'])
print('из них с кэшем Polza: %d' % tot['cache'])
print('из них с пригодным текстовым слоем: %d' % tot['usable'])
print()
print('цена повтора этих %d страниц на PlusVibe: %.2f ₽' % (tot['usable'], tot['cost']))
print()
print('=== страницы, на которых можно судить (кандидаты) ===')
for t in targets:
    print('  %-32s стр.%-3d слой %d знаков, файлов кэша %d'
          % (t['stem'][:32], t['page'], t['layer_len'], len(t['files'])))

json.dump(targets, io.open(r'D:\models\_esc_targets.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
