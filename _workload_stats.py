# -*- coding: utf-8 -*-
"""Measure the real workload: PDF count, page count, text-layer vs scan pages."""
import sys, os, json, glob
sys.path.insert(0, 'D:/models/pylibs')
import pymupdf

DL = r'D:\data-scraping\downloads'
pdfs = sorted(glob.glob(os.path.join(DL, '*.pdf')))
tot = {'files': 0, 'pages': 0, 'text_pages': 0, 'scan_pages': 0, 'mb': 0.0}
per_file = []
for p in pdfs:
    try:
        d = pymupdf.open(p)
    except Exception as e:
        per_file.append((os.path.basename(p), 'OPEN_FAIL', str(e)[:80]))
        continue
    tp = sp = 0
    for pg in d:
        # text layer heuristic: >=120 chars of real text
        t = pg.get_text('text') or ''
        if len(t.strip()) >= 120:
            tp += 1
        else:
            sp += 1
    mb = os.path.getsize(p) / 1e6
    tot['files'] += 1; tot['pages'] += d.page_count
    tot['text_pages'] += tp; tot['scan_pages'] += sp; tot['mb'] += mb
    per_file.append((os.path.basename(p), d.page_count, tp, sp, round(mb, 2)))
    d.close()

print('TOTAL', json.dumps(tot, ensure_ascii=False))
alltext = [f for f in per_file if len(f) == 5 and f[3] == 0]
allscan = [f for f in per_file if len(f) == 5 and f[2] == 0]
mixed   = [f for f in per_file if len(f) == 5 and f[2] > 0 and f[3] > 0]
print(f'fully-text files: {len(alltext)}, fully-scan files: {len(allscan)}, mixed: {len(mixed)}')
print('--- 15 largest scans ---')
for f in sorted(allscan, key=lambda x: -x[2])[:15]:
    print(f'  {f[0][:52]:52} pages={f[1]:3} scan_pages={f[2]:3} {f[4]}MB')
print('--- failures ---')
for f in per_file:
    if len(f) != 5:
        print(' ', f)
json.dump({'total': tot, 'per_file': per_file}, open(r'D:\models\_workload_stats.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
