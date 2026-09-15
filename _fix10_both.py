# -*- coding: utf-8 -*-
r"""Согласие по обоим режимам из кэша (бесплатно).

Режим A: метки всего документа лежат в одном файле `..._detect_run_A{n}_g2_pv.json`.
Режим B: каждая страница лежит отдельно, `..._detect_pg_B{n}_p{стр}_g2_pv.json`.
"""
import io, itertools, json, os, sys

PAGES = r'D:\models\extracted\pages'
GEN = 'g2'
DOCS = [d for d in os.environ.get(
    'FIX10_DOCS', 'НовосибирскАвтодор_6мес_2025|КЛВЗ Кристалл_6мес_2025').split('|') if d]
REPS = int(os.environ.get('FIX10_REPS', '5'))
NP = {'НовосибирскАвтодор_6мес_2025': 49, 'КЛВЗ Кристалл_6мес_2025': 33,
      'ТГК-14_6мес_2025': 41, 'Нижегородец Восток_6мес_2026': 8}
FORM = ('balance', 'income_statement', 'cash_flow')


def load_run(stem, mode, rep, npages):
    if mode == 'A':
        p = os.path.join(PAGES, f'_llm_{stem}_detect_run_A{rep}_{GEN}_pv.json')
        if not os.path.exists(p):
            return None
        pm = json.load(io.open(p, encoding='utf-8'))
        return {r['page']: r.get('form') for r in pm
                if isinstance(r, dict) and isinstance(r.get('page'), int)}
    out = {}
    for p in range(1, npages + 1):
        f = os.path.join(PAGES, f'_llm_{stem}_detect_pg_B{rep}_p{p}_{GEN}_pv.json')
        if not os.path.exists(f):
            return None
        try:
            rec = json.load(io.open(f, encoding='utf-8'))
        except Exception:
            return None
        out[p] = rec.get('form') if isinstance(rec, dict) else None
    return out


print('%-30s %3s %5s %9s %9s %12s %11s'
      % ('документ', 'реж', 'стр.', 'согласие', 'худшая', 'покрытие', 'страниц форм'))
for stem in DOCS:
    npages = NP.get(stem)
    if not npages:
        print('%-30s неизвестно число страниц' % stem[:30]); continue
    for mode in ('A', 'B'):
        runs = {}
        for r in range(1, REPS + 1):
            m = load_run(stem, mode, r, npages)
            if m is not None:
                runs[r] = m
        if len(runs) < 2:
            print('%-30s %3s прогонов готово %d' % (stem[:30], mode, len(runs)))
            continue
        ag, cov, fc = [], [], []
        for r in runs:
            cov.append(sum(1 for p in range(1, npages + 1) if p in runs[r]))
            fc.append(sum(1 for v in runs[r].values() if v in FORM))
        for x, y in itertools.combinations(sorted(runs), 2):
            s = sum(1 for p in range(1, npages + 1) if runs[x].get(p) == runs[y].get(p))
            ag.append(100.0 * s / npages)
        print('%-30s %3s %5d %8.0f%% %8.0f%% %12s %11s'
              % (stem[:30], mode, npages, sum(ag) / len(ag), min(ag),
                 '%d-%d' % (min(cov), max(cov)), '%d-%d' % (min(fc), max(fc))))
        if mode == 'A':
            unstable = [p for p in range(1, npages + 1)
                        if len(set(runs[r].get(p) for r in runs)) > 1]
            print('%-30s     спорных страниц: %d из %d' % ('', len(unstable), npages))
