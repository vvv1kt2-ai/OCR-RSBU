# -*- coding: utf-8 -*-
r"""Нативное разрешение сканов внутри PDF против разрешений рендера (120/200/300 dpi).

Конвейер НЕ читает вложенное изображение напрямую: он рендерит СТРАНИЦУ в заданном
разрешении (`render_png` -> `page.get_pixmap(dpi=dpi)`). Если скан вложен с разрешением
ниже запрошенного, рендер его ИНТЕРПОЛИРУЕТ — новых пикселей не появляется, но
картинка растёт, а с ней растёт и цена (токены изображения).

Считаю нативное разрешение: ширина вложенного изображения (пиксели) / ширина страницы
(дюймы) = dpi скана. Печатаю только сводку, подробности — в CSV.
"""
import os, io, csv, sys, statistics

sys.path.insert(0, r'D:\models')
import pipeline
import pymupdf

SRC = r'D:\data-scraping\downloads'
OUT = r'D:\models\_scan_dpi.csv'

rows = []
for root, _, files in os.walk(SRC):
    for fn in sorted(files):
        if not fn.lower().endswith('.pdf'):
            continue
        path = os.path.join(root, fn)
        try:
            doc = pymupdf.open(path)
        except Exception as e:
            continue
        for i in range(doc.page_count):
            try:
                page = doc[i]
                rect = page.rect
                w_in = rect.width / 72.0
                h_in = rect.height / 72.0
                if w_in <= 0 or h_in <= 0:
                    continue
                imgs = page.get_images(full=True)
                if not imgs:
                    continue
                # берём самое крупное вложенное изображение
                best = None
                for im in imgs:
                    xref = im[0]
                    try:
                        info = doc.extract_image(xref)
                    except Exception:
                        continue
                    w, h = info.get('width') or 0, info.get('height') or 0
                    if not w or not h:
                        continue
                    if best is None or w * h > best[0] * best[1]:
                        best = (w, h, info.get('ext') or '')
                if not best:
                    continue
                w, h, ext = best
                # нативный dpi по ширине и по высоте, берём минимум (консервативно)
                dw = w / w_in
                dh = h / h_in
                native = min(dw, dh)
                rows.append({'file': fn, 'page': i + 1, 'img_w': w, 'img_h': h,
                             'ext': ext, 'page_in_w': round(w_in, 2),
                             'native_dpi': round(native)})
            except Exception:
                continue
        doc.close()

with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    if rows:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)

print('страниц со вложенным изображением: %d (из %d файлов)'
      % (len(rows), len({r['file'] for r in rows})))
if not rows:
    raise SystemExit(0)

nat = [r['native_dpi'] for r in rows]
nat.sort()
print('нативное разрешение скана, dpi: минимум %d, медиана %d, среднее %.0f, максимум %d'
      % (nat[0], nat[len(nat) // 2], statistics.mean(nat), nat[-1]))
print()
print('распределение нативного разрешения:')
buckets = [(0, 100), (101, 150), (151, 200), (201, 250), (251, 300), (301, 400),
           (401, 600), (601, 10 ** 6)]
for lo, hi in buckets:
    k = [d for d in nat if lo <= d <= hi]
    if k:
        bar = '#' * max(1, int(60.0 * len(k) / len(nat)))
        print('  %4d-%-5s %5d стр. %5.1f%%  %s'
              % (lo, '∞' if hi > 10 ** 5 else hi, len(k), 100.0 * len(k) / len(nat), bar))
print()
below = lambda t: sum(1 for d in nat if d < t)
print('страниц, где скан ХУЖЕ разрешения рендера:')
for dpi in (200, 300):
    n = below(dpi)
    print('  ниже %d dpi: %5d стр. (%4.1f%%) — рендер в %d dpi их интерполирует'
          % (dpi, n, 100.0 * n / len(nat), dpi))
print()
print('=== худшие документы (медиана нативного dpi) ===')
by_file = {}
for r in rows:
    by_file.setdefault(r['file'], []).append(r['native_dpi'])
med = sorted(((statistics.median(v), k, len(v)) for k, v in by_file.items()))
print('%-46s %8s %6s' % ('файл', 'медиана', 'страниц'))
for m, k, n in med[:12]:
    print('%-46s %8.0f %6d' % (k[:46], m, n))
print()
print('=== лучшие документы ===')
for m, k, n in med[-6:]:
    print('%-46s %8.0f %6d' % (k[:46], m, n))
print()
print('=== ТГК-14 (пользователь назвал одним из худших) ===')
for r in rows:
    if 'ТГК-14' in r['file']:
        print('  %-34s стр.%-3d %5dx%-5d %s  нативный %d dpi'
              % (r['file'][:34], r['page'], r['img_w'], r['img_h'], r['ext'],
                 r['native_dpi']))
