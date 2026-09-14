# -*- coding: utf-8 -*-
"""Сравнение «с рассуждениями» против «без рассуждений» на одних и тех же страницах.

Третий участник — текстовый слой PDF, единственная бесплатная истина. Он есть лишь
на части страниц, но именно он решает спор: эталон Polza уже уличен в выдумывании
чисел, поэтому «пропало против эталона» само по себе ничего не доказывает.
"""
import io, json, os, re, sys

sys.path.insert(0, r'D:\models')
import _pv_quality as Q
import fitz

PAGES = r'D:\models\extracted\pages'
CACHE = os.path.join(PAGES, '_pvq')
NOR = json.load(io.open(r'D:\models\_reasoning_quality.json', encoding='utf-8'))
WITH = json.load(io.open(r'D:\models\_pv_quality.json', encoding='utf-8'))

wrows = {r['stem']: r for r in WITH['rows']}
nrows = {r['stem']: r for r in NOR['rows']}
common = [s for s in nrows if s in wrows]
print('страниц, где есть оба прогона: %d' % len(common))
print()

# --- текстовый слой ---------------------------------------------------------
def text_layer(pdf, page):
    d = fitz.open(pdf)
    try:
        return d[page - 1].get_text()
    finally:
        d.close()


DL = r'D:\data-scraping\downloads'
print('%-30s %5s | %-22s | %-22s' % ('документ', 'стр', 'с рассуждениями', 'без рассуждений'))
print('%-30s %5s | %6s %6s %6s | %6s %6s %6s'
      % ('', '', 'знач.нет', 'лишн', 'сход', 'знач.нет', 'лишн', 'сход'))
print('-' * 88)
tot = {'w_abs': 0, 'n_abs': 0, 'w_extra': 0, 'n_extra': 0}
for s in sorted(common):
    w, n = wrows[s], nrows[s]
    wex = w['diff']['extra']
    wex = len(wex) if isinstance(wex, (list, tuple)) else wex
    tot['w_abs'] += len(w['absent_sig'])
    tot['n_abs'] += len(n['absent_sig'])
    tot['w_extra'] += wex
    tot['n_extra'] += n['extra']
    print('%-30s %5d | %6d %6d %6.2f | %6d %6d %6.2f'
          % (s[:30], n['page'], len(w['absent_sig']), wex,
             w['ratio'], len(n['absent_sig']), n['extra'], n['ratio']))
print('-' * 88)
print('%-30s %5s | %6d %6d %6s | %6d %6d %6s'
      % ('ИТОГО', '', tot['w_abs'], tot['w_extra'], '', tot['n_abs'], tot['n_extra'], ''))

# --- там, где есть текстовый слой, судит он --------------------------------
print()
print('=== страницы с пригодным текстовым слоем: судит слой, а не эталон ===')
for s in sorted(common):
    n = nrows[s]
    pdf = os.path.join(DL, s + '.pdf')
    if not os.path.exists(pdf):
        continue
    try:
        layer = text_layer(pdf, n['page'])
    except Exception:
        continue
    if len(layer) < 200:
        continue
    lnum = set(Q.norm_digits(layer))
    wn = io.open(os.path.join(CACHE, wrows[s]['pv_file']), encoding='utf-8').read()
    nn = io.open(os.path.join(CACHE, '%s_p%d_%d_noreason.md'
                              % (n['stem'], n['page'], n['dpi'])), encoding='utf-8').read()
    ref = io.open(os.path.join(PAGES, n['ref_file']), encoding='utf-8').read()
    print()
    print('документ %s, стр.%d, слой %d знаков' % (s, n['page'], len(layer)))
    for label, txt in (('Polza (эталон)', ref),
                       ('PlusVibe с рассужд.', wn),
                       ('PlusVibe без рассужд.', nn)):
        nums = [x for x in Q.norm_digits(txt) if len(x) >= 4]
        ok = [x for x in nums if x in lnum]
        bad = [x for x in nums if x not in lnum]
        print('  %-22s чисел %3d, подтверждено слоем %3d, нет в слое %3d %s'
              % (label, len(nums), len(ok), len(bad),
                 ('-> ' + ', '.join(bad[:5])) if bad else ''))
