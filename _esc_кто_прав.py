# -*- coding: utf-8 -*-
r"""Проверяемые случаи: где 300 dpi ошибся, а 200 dpi был прав.

(1) ТГК-14_6мес_2025: эскалация заменила 1250 кол.0 на 11061647. Правило
    1200 = 1210+1215+1220+1230+1240+1250+1260 сходится ТОЧНО на 11081647 и расходится
    ровно на 20000 на 11061647. Нативный dpi той страницы 207, то есть 300 dpi её растянул.
(2) Направление расхождений по всем 72 парам: 300 dpi теряет числа или приобретает, и какие.

Денег не тратит.
"""
import collections
import glob
import io
import os
import re
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

PAGES = r'D:\models\extracted\pages'
NUM = re.compile(r'(?<![\d.,])-?\d[\d \u00a0]{2,}(?:[.,]\d+)?(?![\d])')
pat = re.compile(r'^(?P<doc>.+)_p(?P<pg>\d+)_(?P<dpi>\d+)_(?P<rest>.+)\.md$')


def numbers(text):
    out = set()
    for m in NUM.finditer(text):
        s = m.group(0).replace(' ', '').replace('\u00a0', '').replace(',', '.').lstrip('-')
        if s.endswith('.0'):
            s = s[:-2]
        if s.isdigit():
            out.add(s.lstrip('0') or '0')
    return out


# ---------- (1) ТГК-14 ----------
print('=== (1) ТГК-14_6мес_2025: арифметика решает, кто прав')
art = None
for f in glob.glob(os.path.join(r'D:\models\extracted', 'ТГК-14_6мес_2025.json')):
    import json
    j = json.load(io.open(f, encoding='utf-8'))
    art = j['balance']
print(f"в артефакте 1250 = {[it.get('values') for it in art['items'] if it.get('code')=='1250']}")

for label, fn in (('200 dpi', '_llm_ТГК-14_6мес_2025_struct_balance.json'),
                  ('300 dpi', '_llm_ТГК-14_6мес_2025.pdf_esc_balance.json')):
    p = os.path.join(PAGES, fn)
    if not os.path.exists(p):
        cand = glob.glob(os.path.join(PAGES, f'*ТГК-14_6мес_2025*{fn.split("_")[-1]}*'))
        p = cand[0] if cand else None
    if not p or not os.path.exists(p):
        print(f'  {label}: кэша нет')
        continue
    import json
    j = json.load(io.open(p, encoding='utf-8'))
    vals = {}
    for it in j.get('items') or []:
        if it.get('code'):
            vals[it['code']] = (it.get('values') or [None])[0]
    need = ['1210', '1215', '1220', '1230', '1240', '1250', '1260', '1200']
    have = {c: vals.get(c) for c in need}
    print(f'  {label}: ' + '  '.join(f'{c}={have[c]}' for c in need))
    if all(have[c] is not None for c in need[:-1]) and have['1200'] is not None:
        s = sum(have[c] for c in need[:-1])
        print(f'      сумма = {s}, 1200 = {have["1200"]}, расхождение {s - have["1200"]}')

# ---------- (2) направление расхождений ----------
by = collections.defaultdict(lambda: collections.defaultdict(list))
for f in glob.glob(os.path.join(PAGES, '*_p*_*.md')):
    m = pat.match(os.path.basename(f))
    if m:
        by[(m.group('doc'), int(m.group('pg')))][int(m.group('dpi'))].append(f)

only200 = collections.Counter()
only300 = collections.Counter()
multi = 0
pairs = 0
for k, v in by.items():
    if 300 not in v or 200 not in v:
        continue
    if len(v[200]) > 1:
        multi += 1
    pairs += 1
    t2 = io.open(v[200][0], encoding='utf-8', errors='replace').read()
    t3 = io.open(v[300][0], encoding='utf-8', errors='replace').read()
    s2, s3 = numbers(t2), numbers(t3)
    only200.update(s2 - s3)
    only300.update(s3 - s2)

print()
print(f'=== (2) направление расхождений по {pairs} парам (страниц с >1 файлом 200 dpi: {multi})')
print(f'  чисел только на 200 dpi: {sum(only200.values())} (уникальных {len(only200)})')
print(f'  чисел только на 300 dpi: {sum(only300.values())} (уникальных {len(only300)})')


def big(c):
    return sum(1 for x in c if len(x) >= 4)


print(f'  из них длиной 4+ знака (похожи на значения отчётности): '
      f'только200 {big(only200)}, только300 {big(only300)}')
print('  примеры только на 200 dpi (4+ знака):',
      sorted((x for x in only200 if len(x) >= 4), key=lambda x: -int(x))[:8])
print('  примеры только на 300 dpi (4+ знака):',
      sorted((x for x in only300 if len(x) >= 4), key=lambda x: -int(x))[:8])
