# -*- coding: utf-8 -*-
"""Our own baseline usage, per model, from the run logs: calls, prompt tokens,
completion tokens, and the price we actually paid per 1M tokens. Then the same
token counts priced at PlusVibe rates. Model names are redacted in display, so
each is reported with length and sha1 too."""
import os, re, io, glob, hashlib, json

TMP = r'D:\models\tmp'
pat = re.compile(r'\[llm\]\s+(\S+)\s+pt=(\d+)\s+ct=(\d+)\s+cost=([\d.]+)RUB')
agg = {}
for p in glob.glob(os.path.join(TMP, '*.log')):
    for line in io.open(p, encoding='utf-8', errors='replace'):
        m = pat.search(line)
        if not m:
            continue
        mdl, pt, ct, cost = m.group(1), int(m.group(2)), int(m.group(3)), float(m.group(4))
        a = agg.setdefault(mdl, {'calls': 0, 'pt': 0, 'ct': 0, 'cost': 0.0})
        a['calls'] += 1
        a['pt'] += pt
        a['ct'] += ct
        a['cost'] += cost

print(f'{"model":34} {"len":>4} {"sha1":>11} {"calls":>6} {"pt":>10} {"ct":>10} '
      f'{"costRUB":>9} {"RUB/1M in":>10} {"RUB/1M out":>11}')
rows = []
for mdl, a in sorted(agg.items(), key=lambda x: -x[1]['cost']):
    per_in = a['cost'] / a['pt'] * 1e6 if a['pt'] else 0
    per_out = a['cost'] / a['ct'] * 1e6 if a['ct'] else 0
    rows.append({'model': mdl, 'len': len(mdl),
                 'sha1': hashlib.sha1(mdl.encode()).hexdigest()[:10], **a,
                 'per_in': per_in, 'per_out': per_out})
    print(f'{mdl:34} {len(mdl):>4} {hashlib.sha1(mdl.encode()).hexdigest()[:10]:>11} '
          f'{a["calls"]:>6} {a["pt"]:>10} {a["ct"]:>10} {a["cost"]:>9.2f} '
          f'{per_in:>10.2f} {per_out:>11.2f}')

tot = {k: sum(r[k] for r in rows) for k in ('calls', 'pt', 'ct', 'cost')}
print(f'\nИТОГО вызовов {tot["calls"]}, pt {tot["pt"]}, ct {tot["ct"]}, '
      f'факт {tot["cost"]:.2f} RUB'.encode('ascii', 'replace').decode())
json.dump(rows, io.open(r'D:\models\_pv_usage.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('-> _pv_usage.json')
