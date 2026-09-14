# -*- coding: utf-8 -*-
"""На чём основана проекция на корпус: сколько страниц в пилоте и в корпусе."""
import io, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P          # он же кладёт D:\models\pylibs в sys.path для fitz

DL = r'D:\data-scraping\downloads'
PAGES = r'D:\models\extracted\pages'

pdfs = [f for f in os.listdir(DL) if f.lower().endswith('.pdf')]
print('PDF в корпусе: %d' % len(pdfs))

total = 0
try:
    import fitz
    for f in pdfs:
        d = fitz.open(os.path.join(DL, f))
        total += d.page_count
        d.close()
    print('страниц в корпусе: %d' % total)
except Exception as e:
    print('не удалось посчитать страницы:', e)

# транскрипты: сколько уникальных страниц реально оплачено
pat = re.compile(r'^(.+)_p(\d+)_(\d+)_(.+?)_([0-9a-f]{10})\.md$')
seen = set()
docs = set()
for fn in os.listdir(PAGES):
    m = pat.match(fn)
    if not m or fn.startswith('_'):
        continue
    stem, page, dpi, tag, fp = m.groups()
    seen.add((stem, int(page), int(dpi)))
    docs.add(stem)
print()
print('документов с транскриптами: %d' % len(docs))
pages200 = {(s, p) for (s, p, d) in seen if d == 200}
pages300 = {(s, p) for (s, p, d) in seen if d == 300}
print('уникальных страниц 200 dpi: %d' % len(pages200))
print('уникальных страниц 300 dpi: %d' % len(pages300))
print('уникальных страниц всего: %d' % len(pages200 | pages300))
print()
print('масштаб на корпус:')
print('  по документам: %d / %d = %.1f' % (len(pdfs), len(docs), len(pdfs) / len(docs)))
if total:
    print('  по страницам: %d / %d = %.1f' % (total, len(pages200 | pages300),
                                              total / max(len(pages200 | pages300), 1)))

# Точнее: конвейер сначала определяет, какие страницы нужны, и транскрибирует не все.
# Значит правильный масштаб — не «страниц в корпусе / страниц в пилоте», а «какую долю
# страниц документа пилот реально транскрибировал». Считаем эту долю на его документах.
if total:
    import fitz
    pilot_pages = 0
    missing = 0
    for stem in docs:
        p = os.path.join(DL, stem + '.pdf')
        if not os.path.exists(p):
            missing += 1
            continue
        d = fitz.open(p)
        pilot_pages += d.page_count
        d.close()
    print()
    print('страниц в тех же %d документах, что прошли пилот: %d (не найдено PDF: %d)'
          % (len(docs), pilot_pages, missing))
    if pilot_pages:
        frac = len(pages200 | pages300) / pilot_pages
        print('доля транскрибированных страниц документа: %d / %d = %.2f'
              % (len(pages200 | pages300), pilot_pages, frac))
        est = total * frac
        print('оценка числа страниц, которые будут транскрибированы в корпусе: %.0f'
              % est)
        print()
        print('масштаб по этой доле: %.1f' % (est / len(pages200 | pages300)))
