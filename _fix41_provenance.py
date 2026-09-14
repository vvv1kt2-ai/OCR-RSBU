# -*- coding: utf-8 -*-
"""Whose pages are the orphan 'x_p*_300_*' escalation transcripts?

Prints: page header lines of each x_p file, plus a search for the same numbers
in every final JSON, plus the log lines around the time they were written.
"""
import os, re, glob, json, datetime

PAGES = r'D:\models\extracted\pages'
EX = r'D:\models\extracted'
TMP = r'D:\models\tmp'

xf = sorted(glob.glob(os.path.join(PAGES, 'x_p*')))
print('=== orphan transcript files ===')
for p in xf:
    b = os.path.basename(p)
    txt = open(p, encoding='utf-8').read()
    st = os.stat(p)
    print('\n--- %s  (%d bytes, %s)' % (b.encode('unicode_escape').decode(), st.st_size,
                                        datetime.datetime.fromtimestamp(st.st_mtime)))
    print(txt[:700].replace('\r', ''))

# numbers found in x_p files
nums = set()
for p in xf:
    nums |= set(re.findall(r'\b\d[\d\s]{4,}\b', open(p, encoding='utf-8').read()))
clean = set()
for n in nums:
    n2 = n.replace(' ', '')
    if len(n2) >= 4:
        clean.add(n2)
print('\n=== distinct 4+ digit tokens in orphan transcripts: %d ===' % len(clean))

print('\n=== which final JSON contains these numbers (>=3 hits) ===')
for f in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(f)
    if b.startswith('_'):
        continue
    d = json.load(open(f, encoding='utf-8'))
    flat = json.dumps(d, ensure_ascii=False)
    hits = sorted(n for n in clean if n in flat)
    if len(hits) >= 3:
        print('  %-36s hits=%d  %s' % (b, len(hits), hits[:12]))

print('\n=== tmp logs mentioning the orphan cache / escalation (by mtime 03.09 20:40-22:35) ===')
for f in sorted(glob.glob(os.path.join(TMP, '*.log')) + glob.glob(os.path.join(TMP, '*.txt'))):
    st = os.stat(f)
    dt = datetime.datetime.fromtimestamp(st.st_mtime)
    if dt.strftime('%m-%d') == '09-03':
        print('  LOG %-30s %s %d bytes' % (os.path.basename(f), dt, st.st_size))
