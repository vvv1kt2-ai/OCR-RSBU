# -*- coding: utf-8 -*-
r"""Компактный просмотр транскриптов: что за форма на странице.

Печатает только строки, которые несут смысл: заголовки и строки с кодами 11xx-17xx.
"""
import io, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

STEM = sys.argv[1] if len(sys.argv) > 1 else 'НовосибирскАвтодор_6мес_2025.pdf'
PAGES = [int(x) for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else ['2', '3', '22', '24'])]
N = int(os.environ.get('N', '10'))

doc = P.pymupdf.open(os.path.join(P.DOWNLOADS, STEM))
for p in PAGES:
    txt = P.transcribe_cached(doc, p, STEM, dpi=200, model=P.M_MAIN)
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    print('=' * 74)
    print('СТРАНИЦА %d — всего строк %d' % (p, len(lines)))
    shown = 0
    for l in lines:
        if shown >= N:
            break
        print('   %s' % l[:110])
        shown += 1
doc.close()
