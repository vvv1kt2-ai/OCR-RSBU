# -*- coding: utf-8 -*-
r"""Сравнить один и тот же участок скана при разных разрешениях рендера.

Страница 3 «ТГК-14_6мес_2025» — нативный скан 2000x2424 px при 207 dpi. Именно на ней
эскалация заменила 1250 кол.0 с 11081647 на 11061647. Рендер в 300 dpi здесь
ИНТЕРПОЛИРУЕТ (2550 px из 2000). Делаю вырезки одного участка:
  нативный dpi (~207), 200 dpi, 300 dpi, плюс само вложенное изображение без рендера.
"""
import os, sys

sys.path.insert(0, r'D:\models')
import pipeline
import pymupdf
from PIL import Image
import io as _io

SRC = r'D:\data-scraping\downloads\ТГК-14_6мес_2025.pdf'
OUT = r'D:\models\_dpi_cmp'
PAGE = 3
os.makedirs(OUT, exist_ok=True)

doc = pymupdf.open(SRC)
page = doc[PAGE - 1]
rect = page.rect
print('страница: %.1f x %.1f pt = %.2f x %.2f дюйма'
      % (rect.width, rect.height, rect.width / 72, rect.height / 72))

# вложенное изображение как есть
imgs = page.get_images(full=True)
best = None
for im in imgs:
    info = doc.extract_image(im[0])
    if best is None or info['width'] * info['height'] > best['width'] * best['height']:
        best = info
print('вложенное изображение: %dx%d %s, %d байт'
      % (best['width'], best['height'], best['ext'], len(best['image'])))
native_png = os.path.join(OUT, 'native_embedded.png')
with open(native_png, 'wb') as f:
    f.write(best['image'])

# рендеры страницы
for dpi in (200, 300):
    pix = page.get_pixmap(dpi=dpi)
    p = os.path.join(OUT, 'render_%d.png' % dpi)
    pix.save(p)
    print('рендер %d dpi: %dx%d px -> %s' % (dpi, pix.width, pix.height, os.path.basename(p)))

# нижняя треть страницы (там строки раздела V, включая 1250)
def crop_bottom(path, out, frac=0.34):
    im = Image.open(path)
    w, h = im.size
    box = (0, int(h * (1 - frac)), w, h)
    im.crop(box).save(out)
    print('вырезка %s: %s' % (os.path.basename(out), im.crop(box).size))

crop_bottom(native_png, os.path.join(OUT, 'crop_native.png'))
crop_bottom(os.path.join(OUT, 'render_200.png'), os.path.join(OUT, 'crop_200.png'))
crop_bottom(os.path.join(OUT, 'render_300.png'), os.path.join(OUT, 'crop_300.png'))

# увеличенный фрагмент вокруг правой части строки 1250 — для сравнения «в упор»
for name in ('native', '200', '300'):
    src = os.path.join(OUT, 'crop_%s.png' % name)
    im = Image.open(src)
    w, h = im.size
    # правая половина нижней части — там числовые колонки
    box = (int(w * 0.45), int(h * 0.55), int(w * 0.85), int(h * 0.80))
    f = im.crop(box)
    f = f.resize((f.width * 3, f.height * 3), Image.LANCZOS)
    p = os.path.join(OUT, 'zoom_%s.png' % name)
    f.save(p)
    print('увеличение %s: %s' % (os.path.basename(p), f.size))
doc.close()
