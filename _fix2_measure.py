# -*- coding: utf-8 -*-
r"""Правка 2: измерение на 30 документах, у которых есть кэш старой детекции.

Что делает:
  1. ПЛАТНО (детекция — дешёвая ступень, у пилота 0.22 ₽): прогоняет детекцию с новой
     подсказкой (категории notes и audit) и кладёт результат в кэш `_detect_v2`, то есть
     в тот же ключ, который будет использовать конвейер. Заплаченное переиспользуется.
  2. БЕСПЛАТНО: сверяет новые метки со старыми и проверяет главную опасность правки —
     не потеряла ли форма свои страницы. Проверка идёт по кэшу транскриптов 200 dpi:
     если страница содержит замыкающий код формы (1700/2410/4500), а новая детекция
     назвала её notes/other, это ПОТЕРЯ, и правку в таком виде выпускать нельзя.
"""
import io, os, re, sys, json

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
SRC = r'D:\data-scraping\downloads'
PAGES = P.PAGESDIR
TERMINAL = {'balance': '1700', 'income_statement': '2410', 'cash_flow': '4500'}
TERMINAL_ALT = {'income_statement': ('2410', '2400')}


def find_pdf(stem):
    for root, _, files in os.walk(SRC):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


def label_map(pm):
    out = {}
    for p in pm or []:
        if isinstance(p, dict) and isinstance(p.get('page'), int):
            out[p['page']] = p.get('form')
    return out


def pages_with_terminal(doc, name, form, npages):
    """страницы, в транскрипте которых есть строка замыкающего кода формы (из кэша)"""
    codes = TERMINAL_ALT.get(form, (TERMINAL[form],))
    hits = []
    for p in range(1, npages + 1):
        cp = P.page_cache_path(doc, name, p, 200, P.M_MAIN)
        if not os.path.exists(cp):
            continue
        t = io.open(cp, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'^\s*\|?\s*(\d{4})\s*\|', t, re.M):
            if m.group(1) in codes:
                hits.append(p)
                break
    return hits


old_files = sorted(f for f in os.listdir(PAGES)
                   if re.match(r'^_llm_.+_detect(_pv)?\.json$', f))
LIMIT = int(os.environ.get('FIX2_LIMIT', '0'))
if LIMIT:
    old_files = old_files[:LIMIT]
print('документов со старым кэшем детекции: %d (в этом прогоне: %d)'
      % (len([f for f in os.listdir(PAGES) if re.match(r'^_llm_.+_detect(_pv)?\.json$', f)]),
         len(old_files)))
print()

cost0 = P.USAGE['cost_rub']
calls0 = P.USAGE['calls']
rows = []
for f in old_files:
    stem = re.sub(r'^_llm_', '', f)
    stem = re.sub(r'_detect(_pv)?\.json$', '', stem)
    path = find_pdf(stem)
    if not path:
        print('%-34s PDF не найден' % stem[:34])
        continue
    old = label_map(json.load(io.open(os.path.join(PAGES, f), encoding='utf-8')))
    doc = P.pymupdf.open(path)
    npages = len(doc)
    warns = []
    tag = P.detect_cache_stem(stem + '.pdf')
    try:
        new = label_map(P.cached_llm(tag, lambda: P.detect_pages(
            doc, list(range(1, npages + 1)), npages, warns)))
    except Exception as e:
        print('%-34s ОШИБКА детекции: %s' % (stem[:34], str(e)[:60]))
        doc.close()
        continue

    # страницы, реально содержащие замыкающий код формы
    terminal = {k: pages_with_terminal(doc, os.path.basename(path), k, npages)
                for k in P.FORM_LABELS}
    doc.close()

    lost = []
    for form in P.FORM_LABELS:
        for p in terminal[form]:
            if new.get(p) != form:
                lost.append((form, p, new.get(p)))
    moved_out = {k: sorted(p for p, v in old.items() if v == k and new.get(p) != k)
                 for k in P.FORM_LABELS}
    non_form_old = sorted(p for p, v in old.items() if v in ('notes', 'audit'))
    non_form_new = sorted(p for p, v in new.items() if v in ('notes', 'audit'))
    rows.append({'stem': stem, 'npages': npages, 'lost': lost,
                 'moved_out': moved_out, 'non_form_old': non_form_old,
                 'non_form_new': non_form_new, 'warns': warns})
    flag = 'ПОТЕРЯ' if lost else ('ок' if not any(moved_out.values()) else 'сдвиг')
    print('%-34s стр.%3d  %-7s notes/audit: было %s -> стало %s'
          % (stem[:34], npages, flag, non_form_old, non_form_new))
    for form, p, now in lost:
        print('        ПОТЕРЯ: стр.%d содержит код %s, а помечена %r'
              % (p, TERMINAL[form], now))

cost = P.USAGE['cost_rub'] - cost0
print()
print('=' * 78)
print('цена прогона: %.3f ₽, вызовов %d' % (cost, P.USAGE['calls'] - calls0))
print('документов обработано: %d' % len(rows))
lost_docs = [r for r in rows if r['lost']]
print()
print('ГЛАВНАЯ ПРОВЕРКА — не потеряла ли форма свои страницы:')
print('  документов с потерей: %d' % len(lost_docs))
for r in lost_docs:
    print('     %s: %s' % (r['stem'], r['lost']))
print()
print('страниц с замыкающим кодом, помеченных формой: всего %d'
      % sum(1 for r in rows if not r['lost']))
print()
n_notes = sum(len(r['non_form_new']) for r in rows)
print('найдено страниц notes/audit: %d (было %d)'
      % (n_notes, sum(len(r['non_form_old']) for r in rows)))
print()
print('документы, где из формы ушли страницы:')
n_moved = 0
for r in rows:
    tot = sum(len(v) for v in r['moved_out'].values())
    if tot:
        n_moved += 1
        print('   %-34s %s' % (r['stem'][:34],
                               {k: v for k, v in r['moved_out'].items() if v}))
print('   всего: %d' % n_moved)
json.dump(rows, io.open(r'D:\models\_fix2_measure.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print()
print('подробности: _fix2_measure.json')
