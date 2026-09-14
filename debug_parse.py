# -*- coding: utf-8 -*-
r"""Debug: rule parser output for Rekord trade balance & IS pages."""
import sys, importlib.util
sys.path.insert(0, 'D:/models/pylibs')
import pymupdf
spec = importlib.util.spec_from_file_location('pipeline', r'D:\models\pipeline.py')
pl = importlib.util.module_from_spec(spec)
import os
os.environ['PILOT_OUTDIR'] = r'D:\models\extracted'
spec.loader.exec_module(pl)

doc = pymupdf.open(r'D:\data-scraping\downloads\Рекорд трейд_6мес_2026.pdf')
for key, pages in [('balance', [1, 2, 3]), ('income_statement', [4, 5])]:
    cols, items, warns = pl.structure_text_form(doc, pages, key)
    print(f'===== {key} pages={pages} columns={cols} warns={warns}')
    for it in items:
        print('  ', it.get('code'), it['name'][:45], it['values'])
    ch = pl.run_checks(key, items)
    for c in ch:
        print('  CHECK', c['rule'], c['per_column'])
doc.close()
