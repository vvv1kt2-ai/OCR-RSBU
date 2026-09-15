# -*- coding: utf-8 -*-
r"""Согласие по КОНКРЕТНОЙ форме: совпадает ли набор страниц баланса между прогонами.

Для документов 2025 года нужен только баланс, поэтому важно не общее согласие меток, а
именно согласие по страницам баланса: пропущенная страница баланса = потерянные данные.
"""
import io, itertools, json, os, sys

PAGES = r'D:\models\extracted\pages'
GEN = 'g2'
REPS = int(os.environ.get('FIX10_REPS', '5'))
NP = {'НовосибирскАвтодор_6мес_2025': 49, 'КЛВЗ Кристалл_6мес_2025': 33,
      'ТГК-14_6мес_2025': 41, 'Нижегородец Восток_6мес_2026': 8}
FORM = sys.argv[2] if len(sys.argv) > 2 else 'balance'
STEMS = [sys.argv[1]] if len(sys.argv) > 1 else list(NP)


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
        rec = json.load(io.open(f, encoding='utf-8'))
        out[p] = rec.get('form') if isinstance(rec, dict) else None
    return out


print('форма: %s' % FORM)
print()
print('%-30s %3s %-22s %10s' % ('документ', 'реж', 'страницы формы по прогонам', 'совпало'))
for stem in STEMS:
    npages = NP.get(stem)
    if not npages:
        continue
    for mode in ('A', 'B'):
        sets = []
        for r in range(1, REPS + 1):
            m = load_run(stem, mode, r, npages)
            if m is None:
                continue
            sets.append(sorted(p for p, v in m.items() if v == FORM))
        if len(sets) < 2:
            print('%-30s %3s прогонов готово %d' % (stem[:30], mode, len(sets)))
            continue
        ident = sum(1 for a, b in itertools.combinations(sets, 2) if a == b)
        total = len(list(itertools.combinations(sets, 2)))
        allsame = len(set(map(tuple, sets))) == 1
        shown = sets[0] if allsame else sets[0]
        print('%-30s %3s %-22s %6d из %d пар'
              % (stem[:30], mode, str(shown)[:22], ident, total))
        if not allsame:
            for i, s in enumerate(sets, 1):
                print('%-30s      прогон %d: %s' % ('', i, s))
