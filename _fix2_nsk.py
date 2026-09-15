# -*- coding: utf-8 -*-
r"""Разбор документа, у которого новая детекция потеряла две формы.

НовосибирскАвтодор_6мес_2025: старая подсказка давала 8 страниц форм, новая — 48
страниц баланса из 49, то есть income_statement и cash_flow исчезли. Проверяю, что
там на самом деле, по кэшу транскриптов (бесплатно).
"""
import io, os, re, sys, json

sys.path.insert(0, r'D:\models')
import pipeline as P

PAGES = P.PAGESDIR
SRC = r'D:\data-scraping\downloads'
STEM = 'НовосибирскАвтодор_6мес_2025'

old = json.load(io.open(os.path.join(PAGES, f'_llm_{STEM}_detect.json'), encoding='utf-8'))
new = json.load(io.open(os.path.join(PAGES, f'_llm_{STEM}_detect_v2.json'), encoding='utf-8'))
mo = {p['page']: p['form'] for p in old}
mn = {p['page']: p['form'] for p in new}
npages = max(max(mo), max(mn))
print('страниц: %d' % npages)
print()
print('стр. | старая метка | новая метка')
for p in range(1, npages + 1):
    o, n = mo.get(p), mn.get(p)
    mark = '' if o == n else '   <-- изменилось'
    print('%4d | %-12s | %-12s%s' % (p, o, n, mark))
print()
print('старые страницы форм: %s'
      % {k: sorted(p for p, v in mo.items() if v == k)
         for k in P.FORM_LABELS if any(v == k for v in mo.values())})
print('новые страницы форм:  %s'
      % {k: sorted(p for p, v in mn.items() if v == k)
         for k in P.FORM_LABELS if any(v == k for v in mn.values())})
print()

path = None
for root, _, files in os.walk(SRC):
    for fn in files:
        if os.path.splitext(fn)[0] == STEM:
            path = os.path.join(root, fn)
if not path:
    print('PDF не найден'); sys.exit(0)
doc = P.pymupdf.open(path)
print('что в транскриптах 200 dpi (шапки форм и замыкающие коды):')
for p in range(1, npages + 1):
    cp = P.page_cache_path(doc, os.path.basename(path), p, 200, P.M_MAIN)
    if not os.path.exists(cp):
        print('  стр.%3d: кэша нет' % p); continue
    t = io.open(cp, encoding='utf-8', errors='replace').read()
    heads = re.findall(r'0710\d{3}', t)
    term = [c for c in ('1700', '2400', '2410', '4500') if re.search(r'^\s*\|?\s*%s\s*\|' % c, t, re.M)]
    title = ' | '.join(sorted(set(heads))[:2])
    print('  стр.%3d: формы=%-22s замыкающие=%s' % (p, title or '—', term or '—'))
doc.close()
