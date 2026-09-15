# -*- coding: utf-8 -*-
r"""Откуда взялось значение, которого нет в транскрипте эскалации?

ТГК-14_6мес_2025: эскалация заменила 1250 кол.0 с 11081647 на 11061647, но в транскрипте
стр.3 (и 200, и 300 dpi) стоит 11081647, а 11061647 не встречается вовсе. Проверяю ВСЕ
страницы документа во всех разрешениях и текстовый слой самого PDF.
"""
import io, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline  # добавляет pylibs в sys.path
import pymupdf

PAGES = r'D:\models\extracted\pages'
SRC = r'D:\data-scraping\downloads'
CACHE = re.compile(r'^(?P<stem>.+)_p(?P<p>\d+)_(?P<dpi>\d+)_(?P<rest>.+)\.md$')

STEM = 'ТГК-14_6мес_2025'
OLD, NEW = '11081647', '11061647'


def norm(t):
    return re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', t or '')


print('=== 1. Все транскрипты документа %s ===' % STEM)
rows = []
for f in os.listdir(PAGES):
    m = CACHE.match(f)
    if m and m.group('stem') == STEM:
        t = norm(io.open(os.path.join(PAGES, f), encoding='utf-8').read())
        rows.append((int(m.group('p')), int(m.group('dpi')),
                     OLD in t, NEW in t, len(t)))
for p, dpi, has_old, has_new, n in sorted(rows):
    print('  стр.%-3d %3d dpi, %5d знаков: ошибочное %s | верное %s'
          % (p, dpi, n, 'ЕСТЬ' if has_old else '-', 'ЕСТЬ' if has_new else '-'))
if not any(r[3] for r in rows):
    print('  ВЫВОД: значения 11061647 нет НИ В ОДНОМ транскрипте документа')

print()
print('=== 2. Текстовый слой самого PDF (бесплатно, без OCR) ===')
for root, _, files in os.walk(SRC):
    for fn in files:
        if fn.startswith('ТГК-14_6мес_2025'):
            path = os.path.join(root, fn)
            doc = pymupdf.open(path)
            print('  файл: %s, страниц %d' % (fn, doc.page_count))
            for i in range(doc.page_count):
                t = norm(doc[i].get_text())
                if OLD in t or NEW in t:
                    print('    стр.%-3d текстовый слой: ошибочное %s | верное %s'
                          % (i + 1, 'ЕСТЬ' if OLD in t else '-',
                             'ЕСТЬ' if NEW in t else '-'))
                    j = t.find(OLD) if OLD in t else t.find(NEW)
                    if j >= 0:
                        print('        контекст: ...%s...'
                              % t[max(0, j - 70):j + 25].replace('\n', ' '))
            doc.close()

print()
print('=== 3. Что говорит артефакт ===')
import json
EX = r'D:\models\extracted'
doc = json.load(io.open(os.path.join(EX, STEM + '.json'), encoding='utf-8'))
for it in ((doc.get('balance') or {}).get('items') or []):
    if str(it.get('code')) == '1250':
        print('  код 1250: values=%s' % it.get('values'))
        print('            values_ocr1=%s' % it.get('values_ocr1'))
        print('            corrected_by=%s' % it.get('corrected_by'))
for w in (doc.get('warnings') or []):
    if 'balance' in w:
        print('  warning: %s' % w[:160])
print('  источник: текстовый слой=%s' % (doc.get('source') or {}).get('text_layer'))
