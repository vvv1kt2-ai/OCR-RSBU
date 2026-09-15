# -*- coding: utf-8 -*-
r"""Разбор правки 2 по кэшам меток: старая подсказка против новой.

Читаю оба кэша детекции на каждый документ (`_llm_<док>_detect.json` и
`_llm_<док>_detect_v2.json`) и считаю точно:
  - потерянные формы (не осталось ни одной страницы);
  - страницы с замыкающим кодом формы, помеченные иначе (потеря данных);
  - сколько страниц форм читалось и сколько будет читаться (цена);
  - сколько страниц notes/audit найдено.
Бесплатно: только чтение кэшей.
"""
import io, os, re, sys, json, collections

sys.path.insert(0, r'D:\models')
import pipeline as P

PAGES = P.PAGESDIR
EX = r'D:\models\extracted'
SRC = r'D:\data-scraping\downloads'
TERMINAL = {'balance': '1700', 'income_statement': '2410/2400', 'cash_flow': '4500'}
ALT = {'income_statement': ('2410', '2400'), 'balance': ('1700',), 'cash_flow': ('4500',)}


def find_pdf(stem):
    for root, _, files in os.walk(SRC):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


def labels(path):
    pm = json.load(io.open(path, encoding='utf-8'))
    return {p['page']: p.get('form') for p in pm
            if isinstance(p, dict) and isinstance(p.get('page'), int)}


def terminal_pages(doc, name, form, npages):
    hits = []
    for p in range(1, npages + 1):
        cp = P.page_cache_path(doc, name, p, 200, P.M_MAIN)
        if not os.path.exists(cp):
            continue
        t = io.open(cp, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'^\s*\|?\s*(\d{4})\s*\|', t, re.M):
            if m.group(1) in ALT[form]:
                hits.append(p)
                break
    return hits


stems = sorted(re.sub(r'_detect(_pv)?\.json$', '',
                      f[len('_llm_'):]) for f in os.listdir(PAGES)
               if re.match(r'^_llm_.+_detect(_pv)?\.json$', f))
print('документов с обеими версиями меток: ', end='')
pairs = []
for stem in stems:
    o = os.path.join(PAGES, f'_llm_{stem}_detect.json')
    n = os.path.join(PAGES, f'_llm_{stem}_detect_v2.json')
    if os.path.exists(o) and os.path.exists(n):
        pairs.append((stem, o, n))
print(len(pairs))
print()

lost_form = []
lost_page = []
delta = []
notes_found = []
for stem, o, n in pairs:
    old, new = labels(o), labels(n)
    npages = max(max(old or {0}), max(new or {0}))
    for form in P.FORM_LABELS:
        if any(v == form for v in old.values()) and not any(v == form for v in new.values()):
            lost_form.append((stem, form))
    path = find_pdf(stem)
    if path:
        doc = P.pymupdf.open(path)
        npages = len(doc)
        for form in P.FORM_LABELS:
            for p in terminal_pages(doc, os.path.basename(path), form, npages):
                if new.get(p) != form:
                    lost_page.append((stem, form, p, new.get(p)))
        doc.close()
    old_forms = sum(1 for v in old.values() if v in P.FORM_LABELS)
    new_forms = sum(1 for v in new.values() if v in P.FORM_LABELS)
    delta.append((stem, npages, old_forms, new_forms))
    nn = sorted(p for p, v in new.items() if v in ('notes', 'audit'))
    if nn:
        notes_found.append((stem, nn))

print('=' * 78)
print('1) ПОТЕРЯННЫЕ ФОРМЫ (была форма, не осталось ни одной страницы):')
if not lost_form:
    print('   нет')
for stem, form in lost_form:
    print('   %-34s %s' % (stem[:34], form))
print()

print('2) ПОТЕРЯ ДАННЫХ (страница с замыкающим кодом помечена не формой):')
if not lost_page:
    print('   нет — ни одного случая')
for stem, form, p, now in lost_page:
    print('   %-34s %-17s стр.%-3d код %-9s помечена %r'
          % (stem[:34], form, p, TERMINAL[form], now))
print()

print('3) ЦЕНА: страниц форм читалось -> будет читаться:')
o_tot = sum(d[2] for d in delta)
n_tot = sum(d[3] for d in delta)
print('   всего по %d документам: %d -> %d  (%+d страниц)'
      % (len(delta), o_tot, n_tot, n_tot - o_tot))
print('   оценка цены транскрипции при 0.7 ₽ за страницу эскалации неприменима;')
print('   считаю только число страниц.')
print()
print('   документы, где стало БОЛЬШЕ страниц форм:')
for stem, np_, of, nf in sorted(delta, key=lambda d: -(d[3] - d[2]))[:8]:
    if nf > of:
        print('      %-34s стр.%3d  %d -> %d  (%+d)' % (stem[:34], np_, of, nf, nf - of))
print('   документы, где стало МЕНЬШЕ страниц форм:')
for stem, np_, of, nf in sorted(delta, key=lambda d: (d[3] - d[2]))[:8]:
    if nf < of:
        print('      %-34s стр.%3d  %d -> %d  (%+d)' % (stem[:34], np_, of, nf, nf - of))
print()

print('4) НАЙДЕНО СТРАНИЦ notes/audit: %d в %d документах'
      % (sum(len(v) for _, v in notes_found), len(notes_found)))
print()

print('5) КЛВЗ (случай, ради которого делалась правка):')
for stem, nn in notes_found:
    if stem.startswith('КЛВЗ'):
        print('   %-34s notes/audit: %s' % (stem[:34], nn))
print()
print('6) ДОКУМЕНТЫ, ГДЕ СТРАНИЦЫ ФОРМ ИСЧЕЗЛИ ПОЛНОСТЬЮ ИЛИ ЧАСТИЧНО:')
for stem, np_, of, nf in delta:
    if nf < of:
        print('   %-34s стр.%3d  %d -> %d  (%+d)' % (stem[:34], np_, of, nf, nf - of))
