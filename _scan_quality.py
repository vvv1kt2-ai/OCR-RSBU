# -*- coding: utf-8 -*-
r"""Можно ли оценивать качество скана БЕЗ вызовов LLM — и что это даёт.

Считаю по вложенному изображению (нативные пиксели, без рендера):
  - нативное разрешение (dpi);
  - резкость: дисперсия лапласиана по серому, нормированная на контраст;
  - доля «серых» пикселей: у чёткого текста гистограмма двугорбая, у размытого — серая;
  - разброс угла наклона текста (грубая оценка через профиль проекции).

Никаких вызовов моделей. Пишу CSV, печатаю сводку.
"""
import os, io, csv, sys, math
import numpy as np
from PIL import Image

sys.path.insert(0, r'D:\models')
import pipeline
import pymupdf

SRC = r'D:\data-scraping\downloads'
OUT = r'D:\models\_scan_quality.csv'
LIMIT_PAGES = 400          # выборка: первая страница-скан из каждого документа


def sharpness(gray):
    """дисперсия лапласиана / контраст: выше = резче"""
    a = gray.astype(np.float32)
    lap = (a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1]
           - a[1:-1, :-2] - a[1:-1, 2:])
    sd = float(a.std()) or 1.0
    return float(lap.var()) / (sd * sd)


def gray_ratio(gray):
    """доля пикселей в средней зоне (30..225): у чёткого текста их мало"""
    h = np.histogram(gray, bins=256, range=(0, 256))[0]
    mid = h[30:226].sum()
    return float(mid) / max(1, gray.size)


def skew_estimate(gray):
    """грубая оценка наклона: угол, при котором профиль проекции по строкам острее"""
    small = np.array(Image.fromarray(gray).resize((600, 800)))
    best_angle, best_score = 0.0, -1.0
    for ang in (-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0):
        im = Image.fromarray(small).rotate(ang, resample=Image.BILINEAR, fillcolor=255)
        a = np.asarray(im).astype(np.float32)
        prof = a.mean(axis=1)
        score = float(prof.var())
        if score > best_score:
            best_score, best_angle = score, ang
    return best_angle


rows = []
files = []
for root, _, fs in os.walk(SRC):
    for fn in sorted(fs):
        if fn.lower().endswith('.pdf'):
            files.append(os.path.join(root, fn))

for path in files:
    if len(rows) >= LIMIT_PAGES:
        break
    try:
        doc = pymupdf.open(path)
    except Exception:
        continue
    for i in range(min(doc.page_count, 3)):
        page = doc[i]
        imgs = page.get_images(full=True)
        if not imgs:
            continue
        best = None
        for im in imgs:
            info = doc.extract_image(im[0])
            if best is None or info['width'] * info['height'] > best['width'] * best['height']:
                best = info
        if not best:
            continue
        w_in, h_in = page.rect.width / 72.0, page.rect.height / 72.0
        native = min(best['width'] / w_in, best['height'] / h_in)
        try:
            img = Image.open(io.BytesIO(best['image'])).convert('L')
        except Exception:
            continue
        if img.width < 200:
            continue
        g = np.asarray(img)
        rows.append({'file': os.path.basename(path), 'page': i + 1,
                     'native_dpi': round(native),
                     'px': best['width'] * best['height'],
                     'sharp': round(sharpness(g), 1),
                     'gray_ratio': round(gray_ratio(g), 3),
                     'skew': skew_estimate(g)})
        break
    doc.close()

with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print('документов измерено: %d' % len(rows))
nat = sorted(r['native_dpi'] for r in rows)
sh = sorted(r['sharp'] for r in rows)
gr = sorted(r['gray_ratio'] for r in rows)
print('нативный dpi: медиана %d, 10%% %d, 90%% %d' % (nat[len(nat)//2], nat[len(nat)//10], nat[9*len(nat)//10]))
print('резкость:     медиана %.1f, 10%% %.1f, 90%% %.1f' % (sh[len(sh)//2], sh[len(sh)//10], sh[9*len(sh)//10]))
print('доля серого:  медиана %.3f' % gr[len(gr)//2])
sk = [r['skew'] for r in rows]
from collections import Counter
print('наклон (грубо):', dict(Counter(sk).most_common()))
print()
print('=== низкое нативное разрешение (<150 dpi) ===')
low = [r for r in rows if r['native_dpi'] < 150]
print('документов: %d' % len(low))
for r in sorted(low, key=lambda x: x['native_dpi'])[:10]:
    print('  %-40s %4d dpi  резкость %8.1f  серого %.3f  наклон %+.1f'
          % (r['file'][:40], r['native_dpi'], r['sharp'], r['gray_ratio'], r['skew']))
print()
print('=== самая низкая резкость (размытые сканы) ===')
for r in sorted(rows, key=lambda x: x['sharp'])[:10]:
    print('  %-40s %4d dpi  резкость %8.1f  серого %.3f'
          % (r['file'][:40], r['native_dpi'], r['sharp'], r['gray_ratio']))
print()
print('=== самая высокая доля серого (плохой контраст) ===')
for r in sorted(rows, key=lambda x: -x['gray_ratio'])[:10]:
    print('  %-40s %4d dpi  резкость %8.1f  серого %.3f'
          % (r['file'][:40], r['native_dpi'], r['sharp'], r['gray_ratio']))
print()
print('=== корреляция нативный dpi и резкость ===')
x = np.array([r['native_dpi'] for r in rows], dtype=float)
y = np.array([r['sharp'] for r in rows], dtype=float)
if x.std() > 0 and y.std() > 0:
    print('  пирсон: %.3f' % float(np.corrcoef(x, y)[0, 1]))
