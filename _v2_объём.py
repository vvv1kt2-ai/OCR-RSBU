# -*- coding: utf-8 -*-
r"""Две оставшиеся страницы без кодов + объём работы по всему пилоту (бесплатно, без вызовов).

Часть 1. V2 пометила cash_flow страницы 34 и 35 «НовосибирскАвтодор_6мес_2026», но кодов
строк на них нет. Смотрим, что это, по уже оплаченным транскриптам.

Часть 2. Сколько страниц-кандидатов в пилоте — это верхняя граница того, что вообще может
быть прочитано. Считается без вызовов: кандидат = страница-картинка без текстового слоя
(ровно то, что конвейер передаёт в детекцию).
"""
import io, json, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
PAGES = P.PAGESDIR

# --- часть 1
print('=== стр. 34 и 35 «НовосибирскАвтодор_6мес_2026»')
for p in (33, 34, 35, 36):
    hits = [f for f in os.listdir(PAGES)
            if f.startswith(f'НовосибирскАвтодор_6мес_2026_p{p}_') and f.endswith('.md')]
    if not hits:
        print('  стр. %d — транскрипта нет' % p); continue
    txt = io.open(os.path.join(PAGES, hits[0]), encoding='utf-8').read()
    codes = sorted(set(re.findall(r'\b(?:1[1-7]\d0|2[45]\d0|4[1-5]\d0)\b', txt)))
    body = [l.strip() for l in txt.splitlines() if l.strip()][:3]
    print('  стр. %d: знаков %d, кодов %d' % (p, len(txt), len(codes)))
    for b in body:
        print('      > %s' % b[:150])

# --- часть 2
print()
print('=== кандидаты по пилоту (без вызовов)')
arts = sorted(f for f in os.listdir(OUT) if f.endswith('.json') and not f.startswith('_'))
by_ext = {}
tot_pages = tot_cand = 0
missing = []
for fn in arts:
    stem = os.path.splitext(fn)[0]
    path = None
    for root, _, files in os.walk(P.DOWNLOADS):
        for f2 in files:
            if os.path.splitext(f2)[0] == stem:
                path = os.path.join(root, f2); break
        if path: break
    if not path:
        missing.append(stem); continue
    try:
        doc = P.pymupdf.open(path)
    except Exception as e:
        missing.append('%s (%s)' % (stem, e)); continue
    n = len(doc)
    c = sum(1 for p in range(n)
            if doc[p].get_images(full=True) and len(doc[p].get_text().strip()) < 600)
    doc.close()
    tot_pages += n; tot_cand += c
    ext = os.path.splitext(stem)[-1] if False else None
    by_ext.setdefault(stem[-4:], [0, 0])
    by_ext[stem[-4:]][0] += n
    by_ext[stem[-4:]][1] += c

print('документов: %d (не найдено PDF: %d)' % (len(arts) - len(missing), len(missing)))
if missing:
    print('  нет PDF: %s' % missing[:5])
print('страниц всего: %d' % tot_pages)
print('кандидатов (страницы-картинки): %d' % tot_cand)
print()
print('%-10s %8s %10s %8s' % ('суффикс', 'страниц', 'кандидатов', 'доля'))
for k in sorted(by_ext):
    n, c = by_ext[k]
    print('%-10s %8d %10d %7.0f%%' % (k, n, c, 100.0 * c / max(n, 1)))
print()
print('цена детекции по всем кандидатам пилота: %.2f ₽ (0.00161 ₽ за страницу)'
      % (tot_cand * 0.00161))
