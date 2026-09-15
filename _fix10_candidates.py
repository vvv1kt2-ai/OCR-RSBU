# -*- coding: utf-8 -*-
r"""То же сравнение, но на НАСТОЯЩЕМ наборе кандидатов, как в конвейере.

Замер `_fix10_reps.py` гонял детекцию по всем страницам документа. Реальный конвейер так
не делает: когда в текстовом слое нет форм, а страницы-сканы есть, детекция идёт только по
этим сканам (`scan_pipeline(doc, name, only_pages=img_pages)`). Поэтому вывод надо проверить
на том же наборе, иначе он может не относиться к делу.
"""
import io, itertools, json, os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

PAGES = r'D:\models\extracted\pages'
GEN = 'g2'
STEM = 'НовосибирскАвтодор_6мес_2025'
REPS = 5
FORM = 'balance'

doc = P.pymupdf.open(os.path.join(P.DOWNLOADS, STEM + '.pdf'))
npages = len(doc)
img_pages = [p for p in range(1, npages + 1)
             if doc[p - 1].get_images(full=True) and len(doc[p - 1].get_text().strip()) < 600]
doc.close()
print('документ: %s, страниц %d' % (STEM, npages))
print('кандидатов в конвейере (страницы-сканы): %d — %s' % (len(img_pages), img_pages))
print('исключены из детекции (текстовый слой): %s'
      % [p for p in range(1, npages + 1) if p not in img_pages])
print()


def load_run(mode, rep):
    if mode == 'A':
        p = os.path.join(PAGES, f'_llm_{STEM}_detect_run_A{rep}_{GEN}_pv.json')
        if not os.path.exists(p):
            return None
        pm = json.load(io.open(p, encoding='utf-8'))
        return {r['page']: r.get('form') for r in pm
                if isinstance(r, dict) and isinstance(r.get('page'), int)}
    out = {}
    for p in range(1, npages + 1):
        f = os.path.join(PAGES, f'_llm_{STEM}_detect_pg_B{rep}_p{p}_{GEN}_pv.json')
        if not os.path.exists(f):
            return None
        rec = json.load(io.open(f, encoding='utf-8'))
        out[p] = rec.get('form') if isinstance(rec, dict) else None
    return out


for mode in ('A', 'B'):
    runs = {}
    for r in range(1, REPS + 1):
        m = load_run(mode, r)
        if m is not None:
            runs[r] = m
    if len(runs) < 2:
        print('режим %s: прогонов готово %d' % (mode, len(runs))); continue
    ag = []
    for x, y in itertools.combinations(sorted(runs), 2):
        s = sum(1 for p in img_pages if runs[x].get(p) == runs[y].get(p))
        ag.append(100.0 * s / len(img_pages))
    sets = [sorted(p for p in img_pages if runs[r].get(p) == FORM) for r in sorted(runs)]
    print('режим %s (группы по 8)' % mode if mode == 'A' else 'режим %s (по одной странице)' % mode)
    print('   согласие по кандидатам: среднее %.0f%%, худшая пара %.0f%%'
          % (sum(ag) / len(ag), min(ag)))
    print('   покрытие кандидатов: %s из %d'
          % ([sum(1 for p in img_pages if p in runs[r]) for r in sorted(runs)], len(img_pages)))
    for i, s in enumerate(sets, 1):
        print('   прогон %d: страницы баланса %s' % (i, s))
    found = sum(1 for s in sets if s)
    print('   баланс найден: %d из %d прогонов' % (found, len(sets)))
    print()
