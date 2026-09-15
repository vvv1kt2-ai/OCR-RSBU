# -*- coding: utf-8 -*-
r"""Согласие режима A по готовым прогонам (из кэша, бесплатно)."""
import io, itertools, json, os, sys, collections

PAGES = r'D:\models\extracted\pages'
GEN = 'g2'
DOCS = [d for d in os.environ.get(
    'FIX10_DOCS', 'НовосибирскАвтодор_6мес_2025|КЛВЗ Кристалл_6мес_2025').split('|') if d]
REPS = int(os.environ.get('FIX10_REPS', '5'))
FORM = ('balance', 'income_statement', 'cash_flow')


def load(stem, key):
    p = os.path.join(PAGES, f'_llm_{stem}_detect_run_{key}_{GEN}_pv.json')
    if not os.path.exists(p):
        return None
    pm = json.load(io.open(p, encoding='utf-8'))
    return {r['page']: r.get('form') for r in pm
            if isinstance(r, dict) and isinstance(r.get('page'), int)}


print('режим A (группы по 8 страниц), прогонов %d' % REPS)
print()
print('%-32s %5s %9s %9s %9s %11s %10s'
      % ('документ', 'стр.', 'согласие', 'худшая', 'лучшая', 'покрытие', 'форм'))
for stem in DOCS:
    runs = {}
    for r in range(1, REPS + 1):
        m = load(stem, 'A%d' % r)
        if m is not None:
            runs['A%d' % r] = m
    if len(runs) < 2:
        print('%-32s прогонов мало (%d)' % (stem[:32], len(runs)))
        continue
    npages = max(max(m.keys()) for m in runs.values())
    keys = sorted(runs)
    ag, cov, fc = [], [], []
    for k in keys:
        cov.append(sum(1 for p in range(1, npages + 1) if p in runs[k]))
        fc.append(sum(1 for v in runs[k].values() if v in FORM))
    for x, y in itertools.combinations(keys, 2):
        s = sum(1 for p in range(1, npages + 1) if runs[x].get(p) == runs[y].get(p))
        ag.append(100.0 * s / npages)
    print('%-32s %5d %8.0f%% %8.0f%% %8.0f%% %11s %10s'
          % (stem[:32], npages, sum(ag) / len(ag), min(ag), max(ag),
             '%d-%d' % (min(cov), max(cov)), '%d-%d' % (min(fc), max(fc))))
    # где именно расходится
    base = runs[keys[0]]
    unstable = []
    for p in range(1, npages + 1):
        vals = set(runs[k].get(p) for k in keys)
        if len(vals) > 1:
            unstable.append((p, sorted(str(v) for v in vals)))
    if unstable:
        print('      спорных страниц: %d — %s'
              % (len(unstable), '; '.join('%d:%s' % (p, '/'.join(v)) for p, v in unstable[:10])))
