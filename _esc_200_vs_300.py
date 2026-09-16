# -*- coding: utf-8 -*-
r"""Сравнение чтения 200 dpi (main) и 300 dpi (esc) на ОДНИХ И ТЕХ ЖЕ страницах.

Вопрос: даёт ли 300 dpi более точные ЗНАЧЕНИЯ, если скан внутри PDF почти всегда меньше.
Считаем по множествам чисел, а не глазами: для каждой страницы, которую перечитывала
эскалация, берём транскрипт 200 dpi и транскрипт 300 dpi и сравниваем наборы чисел.

Оговорка: модели у ролей разные (main и esc), поэтому различие наборов — это «200 vs 300
плюс другая модель». Там, где наборы СОВПАЛИ, вопрос снят: 300 dpi не изменил ничего.

Отдельно: сколько перечитанных страниц вообще не имеют скана (чистый текстовый слой) —
для них «нативный dpi» не существует, а 300 dpi растягивает вектор.

Денег не тратит.
"""
import collections
import glob
import io
import os
import re
import sys

PAGES = r'D:\models\extracted\pages'
OUT = r'D:\models\_esc_200_vs_300.md'

NUM = re.compile(r'(?<![\d.,])-?\d[\d \u00a0]{2,}(?:[.,]\d+)?(?![\d])')


def numbers(text):
    """множество чисел страницы в нормализованном виде (без пробелов-разделителей)"""
    out = set()
    for m in NUM.finditer(text):
        s = m.group(0).replace(' ', '').replace('\u00a0', '').replace(',', '.')
        s = s.lstrip('-')
        if s.endswith('.0'):
            s = s[:-2]
        if s.isdigit():
            out.add(s.lstrip('0') or '0')
    return out


pat = re.compile(r'^(?P<doc>.+)_p(?P<pg>\d+)_(?P<dpi>\d+)_(?P<rest>.+)\.md$')

# собрать по (документ, страница) -> {dpi: [файлы]}
by = collections.defaultdict(lambda: collections.defaultdict(list))
for f in glob.glob(os.path.join(PAGES, '*_p*_*.md')):
    m = pat.match(os.path.basename(f))
    if not m:
        continue
    by[(m.group('doc'), int(m.group('pg')))][int(m.group('dpi'))].append(f)

esc_pages = sorted(k for k, v in by.items() if 300 in v)
rows = []
for doc, pg in esc_pages:
    f200 = by[(doc, pg)].get(200) or []
    f300 = by[(doc, pg)].get(300) or []
    if not f200 or not f300:
        rows.append({'doc': doc, 'page': pg, 'state': 'нет пары',
                     'n200': len(f200), 'n300': len(f300)})
        continue
    # берём первый файл каждого dpi (поставщик в имени различается суффиксом)
    t200 = io.open(f200[0], encoding='utf-8', errors='replace').read()
    t300 = io.open(f300[0], encoding='utf-8', errors='replace').read()
    s200, s300 = numbers(t200), numbers(t300)
    rows.append({'doc': doc, 'page': pg, 'state': 'пара',
                 'only200': s200 - s300, 'only300': s300 - s200,
                 'same': s200 == s300, 'n200': len(s200), 'n300': len(s300),
                 'files200': len(f200), 'files300': len(f300)})

pairs = [r for r in rows if r['state'] == 'пара']
same = [r for r in pairs if r['same']]
diff = [r for r in pairs if not r['same']]

lines = []
lines.append('# Эскалация 300 dpi против 200 dpi: что она реально изменила')
lines.append('')
lines.append(f'Страниц, перечитанных эскалацией: **{len(esc_pages)}**. '
             f'С парой транскриптов (200 и 300 dpi): **{len(pairs)}**.')
lines.append('')
lines.append(f'* наборы чисел **совпали** (300 dpi не изменил ничего): **{len(same)}**')
lines.append(f'* наборы чисел **разошлись**: **{len(diff)}**')
lines.append('')
lines.append('Сравнение по множествам чисел; модели у ролей разные (main и esc), поэтому '
             'расхождение — это «200 vs 300 И другая модель», а совпадение снимает вопрос '
             'окончательно: 300 dpi не дал ничего нового.')
lines.append('')
if diff:
    lines.append('## Где наборы разошлись')
    lines.append('')
    lines.append('| документ | стр. | чисел 200 | чисел 300 | только на 200 | только на 300 |')
    lines.append('|---|---|---|---|---|---|')
    for r in sorted(diff, key=lambda r: (r['doc'], r['page'])):
        o2 = ', '.join(sorted(r['only200'])[:6]) or '—'
        o3 = ', '.join(sorted(r['only300'])[:6]) or '—'
        lines.append(f"| {r['doc'][:34]} | {r['page']} | {r['n200']} | {r['n300']} "
                     f"| {o2} | {o3} |")
    lines.append('')
if same:
    lines.append('## Где 300 dpi не изменил ничего')
    lines.append('')
    lines.append('| документ | стр. | чисел |')
    lines.append('|---|---|---|')
    for r in sorted(same, key=lambda r: (r['doc'], r['page'])):
        lines.append(f"| {r['doc'][:34]} | {r['page']} | {r['n200']} |")
    lines.append('')

nopair = [r for r in rows if r['state'] == 'нет пары']
if nopair:
    lines.append('## Перечитаны эскалацией, но пары нет')
    lines.append('')
    for r in nopair:
        lines.append(f"* {r['doc'][:38]} стр.{r['page']} — "
                     f"транскриптов 200 dpi: {r['n200']}, 300 dpi: {r['n300']}")
    lines.append('')

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'страниц перечитано эскалацией: {len(esc_pages)}')
print(f'  с парой 200/300: {len(pairs)}  (совпали {len(same)}, разошлись {len(diff)})')
print(f'  без пары: {len(nopair)}')
print()
print('разошедшиеся (первые 15):')
for r in sorted(diff, key=lambda r: (r['doc'], r['page']))[:15]:
    print(f"  {r['doc'][:30]:30} стр.{r['page']:3} 200->{r['n200']:3} 300->{r['n300']:3}"
          f"  только200={sorted(r['only200'])[:4]} только300={sorted(r['only300'])[:4]}")
print()
print(f'отчёт: {OUT}')
