# -*- coding: utf-8 -*-
r"""Масштаб дефекта: документы, где текстовая ветка не найдёт форм, а формы есть на сканах.

Случай «ИПС_6мес_2026»: PDF смешанный — часть страниц со текстовым слоем, часть сканы. Слой
есть (значит конвейер идёт текстовой веткой), но форм в слое нет: там пояснения. Формы лежат
на страницах-сканах, до которых текстовая ветка не доходит, потому что ей нечего «дополнять» —
она не нашла ни одной формы, чтобы проверить её полноту.

Замер бесплатный: считаем по самому PDF, без единого вызова модели. Признак:
  текстовый слой есть (знаков > 200 и не битый);
  find_form_pages по слою не вернул ни одной страницы формы;
  при этом страницы-сканы в файле есть.
Такие документы в текущем коде выходят пустыми.

Второй, более мягкий признак: в слое формы есть, но не все — тогда работает добор
extra_form_pages (дефект 4.2 уже исправлен) и документ спасается.
"""
import os, sys, re

sys.path.insert(0, r'D:\models')
import pipeline as P

rows = []
for root, _, files in os.walk(P.DOWNLOADS):
    for fn in sorted(files):
        if not fn.lower().endswith('.pdf'):
            continue
        path = os.path.join(root, fn)
        try:
            doc = P.pymupdf.open(path)
        except Exception:
            continue
        n = len(doc)
        chars = sum(len(p.get_text().strip()) for p in doc)
        garbled = [p for p in range(1, n + 1) if P._garbled_page(doc[p - 1])]
        has_text = chars > 200 and len(garbled) < max(2, n // 4)
        img = [p for p in range(1, n + 1)
               if doc[p - 1].get_images(full=True) and len(doc[p - 1].get_text().strip()) < 600]
        if has_text:
            fp = P.find_form_pages(doc)
            fp = {k: list(v) for k, v in fp.items() if v}
        else:
            fp = None
        doc.close()
        rows.append((fn, n, has_text, len(img), fp, chars))

print('документов просмотрено: %d' % len(rows))
print()
text_docs = [r for r in rows if r[2]]
scan_docs = [r for r in rows if not r[2]]
print('идут текстовой веткой: %d; скановой: %d' % (len(text_docs), len(scan_docs)))
print()

empty = [r for r in text_docs if not r[4] and r[3] > 0]
print('=== КРИТИЧНО: текстовая ветка, форм в слое нет, но сканы есть -> документ выйдет пустым')
print('    таких: %d из %d текстовых (%.0f%% всего корпуса)'
      % (len(empty), len(text_docs), 100.0 * len(empty) / max(len(rows), 1)))
for fn, n, _, nimg, fp, chars in empty[:20]:
    print('    %-44s страниц %3d, сканов %3d, знаков слоя %6d'
          % (fn[:44], n, nimg, chars))
if len(empty) > 20:
    print('    ... и ещё %d' % (len(empty) - 20))
print()

mixed = [r for r in text_docs if r[4] and r[3] > 0]
print('=== смешанные, но формы в слое есть (спасает добор): %d' % len(mixed))
print()

full = [r for r in text_docs if r[4] and not r[3]]
print('=== полностью текстовые (форм на сканах нет вовсе): %d' % len(full))
