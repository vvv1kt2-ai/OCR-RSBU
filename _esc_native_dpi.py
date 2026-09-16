# -*- coding: utf-8 -*-
r"""Нативный dpi ИМЕННО ТЕХ страниц, которые реально перечитывала эскалация.

Вопрос пользователя: имеет ли смысл 300 dpi, если исходные сканы в PDF почти всегда
меньше. Здесь не рассуждение, а замер: берём 103 транскрипта 300 dpi (это и есть след
эскалации), для каждой пары (документ, страница) находим самое крупное вложенное
изображение и считаем его нативный dpi. Сравниваем с 300.

Денег не тратит: только pymupdf и имена файлов.
"""
import collections
import glob
import io
import os
import re
import sys

sys.path.insert(0, r'D:\models\pylibs')
import fitz  # noqa: E402

PAGES = r'D:\models\extracted\pages'
DOWN = r'D:\data-scraping\downloads'
OUT = r'D:\models\_esc_native_dpi.csv'

pat = re.compile(r'^(?P<doc>.+)_p(?P<pg>\d+)_(?P<dpi>\d+)_(?P<rest>.+)\.md$')

pairs = []
for f in glob.glob(os.path.join(PAGES, '*_300_*.md')):
    m = pat.match(os.path.basename(f))
    if m:
        pairs.append((m.group('doc'), int(m.group('pg'))))
pairs = sorted(set(pairs))
print(f'страниц, перечитанных эскалацией (документ, страница): {len(pairs)}')

# найти PDF по имени документа
pdfs = {}
for root in (DOWN, r'D:\data-scraping\downloads'):
    for f in glob.glob(os.path.join(root, '**', '*.pdf'), recursive=True):
        pdfs.setdefault(os.path.splitext(os.path.basename(f))[0], f)

rows = []
missing_pdf = collections.Counter()
for doc, pg in pairs:
    path = pdfs.get(doc)
    if not path:
        missing_pdf[doc] += 1
        continue
    try:
        d = fitz.open(path)
        if pg - 1 >= d.page_count:
            d.close()
            continue
        page = d[pg - 1]
        rect = page.rect
        w_in, h_in = rect.width / 72.0, rect.height / 72.0
        best = None
        for im in page.get_images(full=True):
            try:
                info = d.extract_image(im[0])
            except Exception:
                continue
            w, h = info.get('width') or 0, info.get('height') or 0
            if w and h and (best is None or w * h > best[0] * best[1]):
                best = (w, h, info.get('ext') or '')
        d.close()
        if not best or w_in <= 0 or h_in <= 0:
            continue
        w, h, ext = best
        native = min(w / w_in, h / h_in)
        rows.append({'doc': doc, 'page': pg, 'native': round(native),
                     'img_w': w, 'img_h': h, 'ext': ext})
    except Exception:
        continue

with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    f.write('doc;page;native_dpi;img_w;img_h;ext\n')
    for r in rows:
        f.write(f"{r['doc']};{r['page']};{r['native']};{r['img_w']};{r['img_h']};{r['ext']}\n")

nat = sorted(r['native'] for r in rows)
n = len(nat)


def pct(k):
    return nat[min(n - 1, int(n * k))]


print(f'измерено страниц: {n} (нет PDF: {sum(missing_pdf.values())})')
print(f'нативный dpi: минимум {nat[0]}, p25 {pct(.25)}, медиана {pct(.5)}, '
      f'p75 {pct(.75)}, максимум {nat[-1]}')
for thr in (150, 200, 250, 300):
    k = sum(1 for x in nat if x < thr)
    print(f'  ниже {thr:3d} dpi: {k:3d} стр. ({100.0*k/n:4.1f}%) — рендер 300 dpi их растягивает')
k300 = sum(1 for x in nat if x >= 300)
print(f'  с нативным 300+ dpi: {k300} стр. ({100.0*k300/n:.1f}%) — рендер 300 dpi ничего не добавляет')
print()
print('по документам (медиана нативного dpi):')
by = collections.defaultdict(list)
for r in rows:
    by[r['doc']].append(r['native'])
for d, v in sorted(by.items(), key=lambda kv: sorted(kv[1])[len(kv[1]) // 2]):
    print(f'  {d[:38]:38} стр.{len(v):3d}  медиана {sorted(v)[len(v)//2]:3d}  '
          f'мин {min(v):3d}  макс {max(v):3d}')
print()
print(f'подробности: {OUT}')
