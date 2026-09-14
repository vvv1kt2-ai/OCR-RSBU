# -*- coding: utf-8 -*-
"""Correlate finish_reason=length (truncated generation) with the documents whose
structured JSON came out incomplete, and inspect the raw struct cache artifacts."""
import os, re, glob, json, collections

doc_re = re.compile(r'\[(\d+)/(\d+)\]\s+(.+?\.pdf)')
llm_re = re.compile(r'\[llm\]\s+(\S+)\s+pt=(\d+)\s+ct=(\d+)\s+cost=([\d.]+)RUB\s+(\d+)s\s+finish=(\S+)')

trunc_by_doc = collections.defaultdict(list)
call_by_doc = collections.defaultdict(int)
for lg in sorted(glob.glob(r'D:\models\tmp\*.log')):
    cur = os.path.basename(lg)
    for line in open(lg, encoding='utf-8', errors='replace'):
        m = doc_re.search(line)
        if m:
            cur = m.group(3)
            continue
        m2 = llm_re.search(line)
        if m2:
            call_by_doc[cur] += 1
            if m2.group(6) != 'stop':
                trunc_by_doc[cur].append((m2.group(1), int(m2.group(3)), m2.group(6)))

print('=== calls with finish != stop, by document ===')
for d, v in sorted(trunc_by_doc.items(), key=lambda x: -len(x[1])):
    print(f'  {d[:60]:60} n={len(v)} calls={call_by_doc[d]}')
    for model, ct, fin in v:
        print(f'        {model:32} completion_tokens={ct:6} finish={fin}')

print('\n=== struct cache artifacts: size and tail ===')
for f in sorted(glob.glob(r'D:\models\extracted\pages\*_struct_*.json')):
    b = os.path.basename(f)
    sz = os.path.getsize(f)
    try:
        raw = open(f, encoding='utf-8').read()
    except Exception as e:
        print(' ', b, 'READ_FAIL', e); continue
    ok = True
    try:
        json.loads(raw)
    except Exception:
        ok = False
    if sz < 400 or not ok:
        print(f'  {b[:70]:70} {sz:7}B json_ok={ok} tail={raw[-90:]!r}')

print('\n=== extracted/*.json: item counts per form (find truncated ones) ===')
for f in sorted(glob.glob(r'D:\models\extracted\*.json')):
    b = os.path.basename(f)
    if b.startswith('_'):
        continue
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception as e:
        print(f'  {b}: PARSE_FAIL {e}'); continue
    forms = d.get('forms') or {}
    parts = []
    for k, v in forms.items():
        items = (v or {}).get('items') or []
        parts.append(f'{k}={len(items)}')
    st = d.get('status')
    if st != 'ok':
        print(f'  {b[:52]:52} status={st:14} {" ".join(parts)}')
