# -*- coding: utf-8 -*-
r"""Precise post-migration check.

Two questions:
  1. Is there any page transcript on disk still lacking the fingerprint suffix?
     (i.e. did the migration miss a file that should have been renamed)
  2. For pages the pipeline actually transcribed at 200 dpi, does the new key hit?
     Pages of text-branch documents were never transcribed at 200 dpi, so they are
     expected to be absent — those are not misses.
"""
import os, re, sys, json, glob

sys.path.insert(0, r'D:\models')
import pipeline as P

PAGES = os.path.join(P.OUTDIR, 'pages')
OUT = []

page_shape = re.compile(r'^.+_p\d+_(200|300)_.*\.md$')
with_fp = re.compile(r'^.+_p\d+_(200|300)_.*_[0-9a-f]{10}\.md$')

all_page = [n for n in os.listdir(PAGES)
            if os.path.isfile(os.path.join(PAGES, n)) and page_shape.match(n)]
unmigrated = [n for n in all_page if not with_fp.match(n)]
OUT.append('1. транскриптов страниц на диске        : %d' % len(all_page))
OUT.append('   из них без отпечатка (не мигрировали): %d' % len(unmigrated))
for n in unmigrated[:20]:
    OUT.append('      %s' % n.encode('unicode_escape').decode())

hit = 0
absent_by_design = 0
only_300 = []
real_miss = []
for f in sorted(glob.glob(os.path.join(P.OUTDIR, '*.json'))):
    b = os.path.basename(f)
    if b.startswith('_'):
        continue
    stem = b[:-5]
    pdf = os.path.join(P.DOWNLOADS, stem + '.pdf')
    if not os.path.exists(pdf):
        continue
    d = json.load(open(f, encoding='utf-8'))
    pages = set()
    for form in ('balance', 'income_statement', 'cash_flow'):
        for p in ((d.get(form) or {}).get('transcript_pages') or []):
            if isinstance(p, int):
                pages.add(p)
    doc = P.pymupdf.open(pdf)
    for p in sorted(pages):
        want = P.page_cache_path(doc, stem + '.pdf', p, 200, P.M_MAIN)
        if os.path.exists(want):
            hit += 1
            continue
        # is there any transcript at all for this doc/page, at any dpi?
        any_dpi = [n for n in os.listdir(PAGES)
                   if n.startswith('%s_p%d_' % (stem, p)) and n.endswith('.md')]
        at_200 = [n for n in any_dpi if re.match(r'^.+_p\d+_200_.*\.md$', n)]
        if at_200:
            # a 200 dpi transcript existed and still does not match the new key: real miss
            real_miss.append((stem, p, at_200[:2]))
        elif any_dpi:
            only_300.append((stem, p, any_dpi[:2]))
        else:
            absent_by_design += 1
    doc.close()

OUT.append('')
OUT.append('2. страниц, реально транскрибированных на 200 dpi: попаданий %d' % hit)
OUT.append('   отсутствуют, потому что транскрипта не было вовсе: %d' % absent_by_design)
OUT.append('   есть только 300 dpi (текстовая ветка + эскалация)  : %d' % len(only_300))
OUT.append('   НАСТОЯЩИХ промахов (был 200 dpi, ключ не тот)      : %d' % len(real_miss))
for stem, p, names in real_miss[:20]:
    OUT.append('      %s стр.%d -> %s' % (stem, p, [x.encode('unicode_escape').decode() for x in names]))

open(r'D:\models\_dbg_cachehit2.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('unmigrated=%d real_miss=%d absent_by_design=%d'
      % (len(unmigrated), len(real_miss), absent_by_design))
