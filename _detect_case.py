# -*- coding: utf-8 -*-
r"""Разбор одного случая: правда ли детекция путает формы, или врёт мой классификатор.

Проверяет три вещи, каждая из которых могла дать ложное расхождение:
  1. читаю ли я транскрипт ТОГО ЖЕ файла (отпечаток PDF в имени) или устаревший;
  2. сколько транскриптов вообще лежит на одну страницу (дубли с разными отпечатками);
  3. что на самом деле написано в шапке транскрипта.
"""
import io, os, re, sys, hashlib, json

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR
import fitz

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
DL = r'D:\data-scraping\downloads'

DOCS = ['Артген (ИСКЧ)_6мес_2025', 'КЛВЗ Кристалл_6мес_2025']
MAIN_TAG = P.model_tag(P.M_MAIN)

TR = re.compile(r'^(.+)_p(\d+)_200_(.+?)_([0-9a-f]{10})\.md$')


def files_for(stem, page, tag=MAIN_TAG):
    out = []
    for fn in os.listdir(PAGES):
        m = TR.match(fn)
        if m and m.group(1) == stem and int(m.group(2)) == page and m.group(3) == tag:
            out.append((fn, m.group(4)))
    return out


for stem in DOCS:
    pdf = os.path.join(DL, stem + '.pdf')
    if not os.path.exists(pdf):
        print('нет PDF: %s' % stem)
        continue
    d = fitz.open(pdf)
    fp = P.doc_fingerprint(d)
    res = json.load(io.open(os.path.join(EX, stem + '.json'), encoding='utf-8'))
    print('=' * 78)
    print('%s  (страниц %d, отпечаток %s)' % (stem, d.page_count, fp))
    for form in ('balance', 'income_statement', 'cash_flow'):
        tp = (res.get(form) or {}).get('transcript_pages')
        print('  %-17s страницы: %s' % (form, tp))
    print()
    print('  разбор страниц, попавших в balance:')
    for p in ((res.get('balance') or {}).get('transcript_pages') or []):
        if not isinstance(p, int):
            continue
        fs = files_for(stem, p)
        marks = []
        for fn, f in fs:
            marks.append('%s%s' % (f, ' (текущий)' if f == fp else ' (СТАРЫЙ)'))
        print('    стр.%-3d файлов %d: %s' % (p, len(fs), ', '.join(marks) or 'нет'))
        # текст слоя страницы — независимый судья
        layer = d[p - 1].get_text() if 1 <= p <= d.page_count else ''
        codes = [c for c in ('0710001', '0710002', '0710004', '0710005')
                 if c in layer]
        print('        текстовый слой: %d знаков, коды %s' % (len(layer), codes or 'нет'))
        if fs:
            fn = [x for x in fs if x[1] == fp] or [fs[0]]
            txt = io.open(os.path.join(PAGES, fn[0][0]), encoding='utf-8').read()
            head = re.sub(r'\s+', ' ', txt[:260])
            print('        транскрипт: %s' % head)
    d.close()
