# -*- coding: utf-8 -*-
r"""Воспроизводимость детекции: несколько прогонов на режим, попарное сравнение.

Почему не двух прогонов достаточно: детекция недетерминирована, поэтому сравнение одной
пары — это одно наблюдение. Первая пара на «НовосибирскАвтодор_6мес_2025» дала 71%
совпадения, вторая (уже настоящим кодом конвейера) — 100%. Чтобы получить число, а не
случайную величину, здесь N прогонов на режим и усреднение по ВСЕМ парам.

Режимы:
  A — как в конвейере: P.detect_pages, группы по 8 страниц;
  B — по одной странице за вызов.

Показатели на режим:
  * согласие — средняя доля страниц с одинаковой меткой по всем парам прогонов;
  * покрытие — сколько страниц получили метку, в каждом прогоне;
  * разброс числа страниц форм между прогонами.

Прогоны кэшируются по тегам, поэтому повторы бесплатны, а уже сделанные прогоны
(поколение g2) переиспользуются.
"""
import io, itertools, json, os, re, sys, collections

sys.path.insert(0, r'D:\models')
import pipeline as P

SRC = r'D:\data-scraping\downloads'
DOCS = [d for d in os.environ.get(
    'FIX10_DOCS', 'НовосибирскАвтодор_6мес_2025|КЛВЗ Кристалл_6мес_2025').split('|') if d]
MODES = [m for m in os.environ.get('FIX10_MODES', 'A,B').split(',') if m]
REPS = int(os.environ.get('FIX10_REPS', '5'))
GEN = 'g2'


def find_pdf(stem):
    for root, _, files in os.walk(SRC):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


def labels_of(pm):
    return {p['page']: p.get('form') for p in (pm or [])
            if isinstance(p, dict) and isinstance(p.get('page'), int)}


def detect_per_page(doc, npages, warnings, stem, rep):
    """по одной странице за вызов; результат каждой страницы кэшируется отдельно.

    Кэш на страницу, а не на прогон: прогон из 49 вызовов, упавший на 40-м, не должен
    терять 39 оплаченных ответов. И повторный запуск скрипта тогда бесплатен.
    """
    from concurrent.futures import ThreadPoolExecutor

    def one(p):
        def call():
            cm = [{'role': 'user', 'content': [
                {'type': 'text', 'text': P.DETECT_PROMPT +
                 f' Это одна страница: страница {p} из {npages}.'},
                *P.img_parts(P.render_png(doc[p - 1], 120), f'СТРАНИЦА {p}')]}]
            try:
                txt, _ = P.chat(cm, P.M_DETECT, temperature=0, max_tokens=2000)
            except Exception as e:
                warnings.append(f'page {p}: {e}')
                return {'page': p, 'form': 'unknown'}
            pm = P.salvage_pages_map(txt, npages)
            if pm:
                hit = [r for r in pm if r['page'] == p]
                return hit[0] if hit else {'page': p, 'form': pm[0].get('form')}
            m = re.search(r'"\s*\d*\s*"\s*:\s*"(\w+)"', txt) or \
                re.search(r'\b(balance|income_statement|cash_flow|other|notes|audit)\b', txt)
            return {'page': p, 'form': m.group(1) if m else 'unknown'}
        return P.cached_llm(f'{stem}_detect_pg_{mode}{rep}_p{p}_{GEN}', call)

    with ThreadPoolExecutor(max_workers=4) as ex:
        return list(ex.map(one, range(1, npages + 1)))


def fcount(m):
    return sum(1 for v in m.values() if v in P.FORM_LABELS)


cost0, calls0 = P.USAGE['cost_rub'], P.USAGE['calls']
summary = []
for stem in DOCS:
    path = find_pdf(stem)
    if not path:
        print('%s: PDF не найден' % stem); continue
    doc = P.pymupdf.open(path)
    npages = len(doc)
    print('=' * 78)
    print('%s — %d страниц, режимы %s, прогонов на режим %d' % (stem, npages, MODES, REPS))
    warnings = []
    runs = {}
    for mode in MODES:
        for rep in range(1, REPS + 1):
            key = f'{mode}{rep}'
            # own tag namespace: a whole-run file from another script must never be picked
            # up here, or a cached result of unknown provenance would be counted as a run
            tag = f'{stem}_detect_run_{key}_{GEN}'
            if mode == 'A':
                fn = lambda: P.detect_pages(doc, list(range(1, npages + 1)), npages, warnings)
            else:
                fn = lambda: detect_per_page(doc, npages, warnings, stem, rep)
            try:
                pm = P.cached_llm(tag, fn)
            except Exception as e:
                print('   %s УПАЛ: %s' % (key, str(e)[:100]))
                pm = []
            runs[key] = labels_of(pm)
        keys = [f'{mode}{r}' for r in range(1, REPS + 1) if f'{mode}{r}' in runs]
        covs = [sum(1 for p in range(1, npages + 1) if p in runs[k]) for k in keys]
        fcs = [fcount(runs[k]) for k in keys]
        pairs = list(itertools.combinations(keys, 2))
        agree = []
        for x, y in pairs:
            s = sum(1 for p in range(1, npages + 1) if runs[x].get(p) == runs[y].get(p))
            agree.append(100.0 * s / npages)
        mean = sum(agree) / len(agree) if agree else 0.0
        worst = min(agree) if agree else 0.0
        print('   режим %s: согласие по %d парам — среднее %.0f%%, худшая пара %.0f%%'
              % (mode, len(pairs), mean, worst))
        print('             покрытие: %s' % covs)
        print('             страниц форм: %s (разброс %d)'
              % (fcs, max(fcs) - min(fcs) if fcs else 0))
        summary.append((stem, mode, npages, mean, worst, covs, fcs))
    doc.close()

cost = P.USAGE['cost_rub'] - cost0
calls = P.USAGE['calls'] - calls0
print()
print('=' * 78)
print('цена замера: %.3f ₽, вызовов %d' % (cost, calls))
print()
print('%-32s %3s %10s %10s %14s %10s'
      % ('документ', 'реж', 'согласие', 'худшая', 'покрытие', 'форм разброс'))
for stem, mode, n, mean, worst, covs, fcs in summary:
    print('%-32s %3s %9.0f%% %9.0f%% %14s %10d'
          % (stem[:32], mode, mean, worst,
             '%d-%d из %d' % (min(covs), max(covs), n),
             max(fcs) - min(fcs) if fcs else 0))
print()
print('Читать так: согласие 100% = метки не зависят от случая; покрытие ниже 100% =')
print('страницы, о которых прогон не сказал ничего и которые не будут прочитаны.')
