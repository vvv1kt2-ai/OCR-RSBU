# -*- coding: utf-8 -*-
"""Summarize extracted/*.json: statuses, models, checks, page-cache breakdown."""
import os, re, json, glob, collections

EX = r'D:\models\extracted'
st = collections.Counter(); models = collections.Counter()
bad = []; srcs = collections.Counter(); branch = collections.Counter()
for f in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(f)
    if b.startswith('_'):
        continue
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception as e:
        bad.append((b, 'PARSE_FAIL', str(e)[:60])); continue
    s = d.get('status') or (d.get('meta') or {}).get('status') or 'MISSING'
    st[s] += 1
    src = d.get('source') or {}
    if isinstance(src, dict):
        m = src.get('ocr_model')
        if m: models[m] += 1
        for k in src:
            srcs[k] += 1
    br = d.get('branch') or (d.get('meta') or {}).get('branch')
    if br: branch[br] += 1
    if s not in ('ok',):
        bad.append((b, s, ''))

print('files:', sum(st.values()))
print('status:', dict(st))
print('branch:', dict(branch))
print('source keys:', dict(srcs))
print('ocr_model:', dict(models))
print('--- non-ok ---')
for x in bad[:60]:
    print('  ', x)

# page cache breakdown
pg = os.path.join(EX, 'pages')
names = [n for n in os.listdir(pg) if os.path.isfile(os.path.join(pg, n))]
c = collections.Counter(); dpi = collections.Counter(); kinds = collections.Counter()
for n in names:
    m = re.match(r'^(?P<doc>.+?)_p(?P<p>\d+)_(?P<dpi>\d+)_(?P<model>[^_]+(?:_[^_]+)*)\.md$', n)
    if m:
        dpi[m.group('dpi')] += 1; c[m.group('model')] += 1; kinds['page'] += 1
    else:
        kinds[re.sub(r'[^a-zA-Z_]+', '#', n)[:40]] += 1
print('page cache files:', len(names), 'parsed:', kinds['page'])
print('by dpi:', dict(dpi))
print('by model token:', dict(c))
print('unparsed name shapes:', {k: v for k, v in kinds.items() if k != 'page'})
print('sample names:', names[:5])
