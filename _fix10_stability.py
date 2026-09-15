# -*- coding: utf-8 -*-
r"""Воспроизводимость детекции на plusvibe: группы по 8 страниц против по одной.

Вопрос: выбор страниц формы опирается на один вызов детекции, а он на polza оказался
невоспроизводимым. Целевой прогон идёт на plusvibe, где модель детекции ДРУГАЯ
(deepseek-v4.1-flash), поэтому мерить надо здесь.

Режимы (по два независимых прогона каждый):
  A — как в конвейере: P.detect_pages, группы по 8 страниц;
  B — по одной странице за вызов (в конвейере такого режима пока нет).

Что измеряю на каждом прогоне:
  * покрытие — сколько страниц вообще получили метку (пропуск страницы означает, что
    страница формы может не попасть в чтение вообще);
  * число страниц форм;
  * согласие двух прогонов по каждой странице.

Страница, которую не удалось разобрать, помечается `unknown`, а НЕ `other`: `other`
скрыл бы потерю, а `unknown` её показывает.
"""
import io, json, os, re, sys, collections

sys.path.insert(0, r'D:\models')
import pipeline as P

SRC = r'D:\data-scraping\downloads'
DOCS = ['НовосибирскАвтодор_6мес_2025', 'КЛВЗ Кристалл_6мес_2025',
        'ТГК-14_6мес_2025']
if os.environ.get('FIX10_DOCS'):
    DOCS = [d for d in os.environ['FIX10_DOCS'].split('|') if d]
CH = 8
GEN = 'g2'          # поколение тегов: результаты привязаны к версии кода


def find_pdf(stem):
    for root, _, files in os.walk(SRC):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


def labels_of(pm):
    return {p['page']: p.get('form') for p in (pm or [])
            if isinstance(p, dict) and isinstance(p.get('page'), int)}


def detect_per_page(doc, npages, warnings):
    """по одной странице за вызов; неудача помечается unknown, а не other"""
    pages_map = []
    for p in range(1, npages + 1):
        cm = [{'role': 'user', 'content': [
            {'type': 'text', 'text': P.DETECT_PROMPT +
             f' Это одна страница: страница {p} из {npages}.'},
            *P.img_parts(P.render_png(doc[p - 1], 120), f'СТРАНИЦА {p}')]}]
        try:
            txt, _ = P.chat(cm, P.M_DETECT, temperature=0, max_tokens=2000)
        except Exception as e:
            warnings.append(f'page {p}: {e}')
            pages_map.append({'page': p, 'form': 'unknown'})
            continue
        pm = P.salvage_pages_map(txt, npages)
        if pm:
            hit = [r for r in pm if r['page'] == p]
            pages_map.append(hit[0] if hit else {'page': p, 'form': pm[0].get('form')})
            continue
        m = re.search(r'"\s*\d*\s*"\s*:\s*"(\w+)"', txt) or \
            re.search(r'\b(balance|income_statement|cash_flow|other|notes|audit)\b', txt)
        pages_map.append({'page': p, 'form': m.group(1) if m else 'unknown'})
    return pages_map


def form_counts(m):
    return dict(collections.Counter(v for v in m.values() if v in P.FORM_LABELS))


def coverage(m, npages):
    return sum(1 for p in range(1, npages + 1) if p in m)


cost0, calls0 = P.USAGE['cost_rub'], P.USAGE['calls']
results = []
for stem in DOCS:
    path = find_pdf(stem)
    if not path:
        print('%s: PDF не найден' % stem); continue
    doc = P.pymupdf.open(path)
    npages = len(doc)
    print('=' * 78)
    print('%s — %d страниц' % (stem, npages))
    warnings = []
    runs = {}
    for mode in ('A', 'B'):
        for rep in (1, 2):
            key = f'{mode}{rep}'
            tag = f'{stem}_detect_{key}_{GEN}'
            if mode == 'A':
                fn = lambda: P.detect_pages(doc, list(range(1, npages + 1)), npages, warnings)
            else:
                fn = lambda: detect_per_page(doc, npages, warnings)
            try:
                pm = P.cached_llm(tag, fn)
            except Exception as e:
                print('   прогон %s УПАЛ: %s' % (key, str(e)[:110]))
                pm = []
            runs[key] = labels_of(pm)
            cov = coverage(runs[key], npages)
            print('   %s: покрытие %d/%d, страниц форм %s, unknown %d'
                  % (key, cov, npages, form_counts(runs[key]),
                     sum(1 for v in runs[key].values() if v == 'unknown')))
    doc.close()

    same_a = sum(1 for p in range(1, npages + 1) if runs['A1'].get(p) == runs['A2'].get(p))
    same_b = sum(1 for p in range(1, npages + 1) if runs['B1'].get(p) == runs['B2'].get(p))
    print('   A (группы по 8): совпало %d из %d (%.0f%%)' % (same_a, npages, 100.0*same_a/npages))
    print('   B (по одной):    совпало %d из %d (%.0f%%)' % (same_b, npages, 100.0*same_b/npages))
    results.append((stem, npages, same_a, same_b,
                    coverage(runs['A1'], npages), coverage(runs['B1'], npages)))

cost = P.USAGE['cost_rub'] - cost0
calls = P.USAGE['calls'] - calls0
print()
print('=' * 78)
print('цена замера: %.3f ₽, вызовов %d' % (cost, calls))
print()
print('%-34s %6s %11s %11s %11s' % ('документ', 'стр.', 'A совпало', 'B совпало', 'покрытие A1'))
for stem, n, sa, sb, ca, cb in results:
    print('%-34s %6d %10.0f%% %10.0f%% %11s' % (stem[:34], n, 100.0*sa/n, 100.0*sb/n, '%d/%d' % (ca, n)))
if results:
    tn = sum(r[1] for r in results)
    ta = sum(r[2] for r in results); tb = sum(r[3] for r in results)
    print('%-34s %6d %10.0f%% %10.0f%%' % ('ИТОГО', tn, 100.0*ta/tn, 100.0*tb/tn))
print()
print('Читать так: 100% = детекция воспроизводится; покрытие меньше 100% =')
print('страницы, о которых прогон не сказал ничего.')
