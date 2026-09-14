# -*- coding: utf-8 -*-
"""Parse tmp/*.log for '[llm] ... cost=..RUB ..s' lines: real measured cost and latency."""
import os, re, glob, collections, statistics

LOGS = glob.glob(r'D:\models\tmp\*.log')
pat = re.compile(r'\[llm\]\s+(\S+)\s+pt=(\d+)\s+ct=(\d+)\s+cost=([\d.]+)RUB\s+(\d+)s(?:\s+finish=(\S+))?')
tot = collections.Counter(); calls = 0; per_model = collections.defaultdict(lambda: {'n': 0, 'pt': 0, 'ct': 0, 'cost': 0.0, 'secs': []})
fin = collections.Counter(); perlog = {}
for lg in sorted(LOGS):
    n = 0; c = 0.0; s = 0
    for line in open(lg, encoding='utf-8', errors='replace'):
        m = pat.search(line)
        if not m:
            continue
        model, pt, ct, cost, sec, f = m.group(1), int(m.group(2)), int(m.group(3)), float(m.group(4)), int(m.group(5)), m.group(6)
        calls += 1; n += 1; c += cost; s += sec
        d = per_model[model]; d['n'] += 1; d['pt'] += pt; d['ct'] += ct; d['cost'] += cost; d['secs'].append(sec)
        fin[f] += 1
    if n:
        perlog[os.path.basename(lg)] = (n, round(c, 2), s)

print(f'parsed LLM calls: {calls}')
print(f'TOTAL measured cost across all logs: {sum(d["cost"] for d in per_model.values()):.2f} RUB')
print(f'TOTAL measured LLM wall-time (sum of per-call seconds): {sum(sum(d["secs"]) for d in per_model.values())} s')
print('finish_reason:', dict(fin))
print('\nper model:')
for m, d in sorted(per_model.items(), key=lambda x: -x[1]['cost']):
    ss = sorted(d['secs'])
    print(f'  {m:34} calls={d["n"]:4} pt={d["pt"]:9} ct={d["ct"]:9} cost={d["cost"]:8.2f}RUB '
          f'lat_med={statistics.median(ss):5.0f}s lat_p90={ss[int(len(ss)*0.9)-1]:5.0f}s lat_max={max(ss):5}s')
print('\nper log (calls, RUB, sum-seconds):')
for k, v in perlog.items():
    print(f'  {k:22} {v}')
print('\ncost per call by model:')
for m, d in per_model.items():
    print(f'  {m:34} {d["cost"]/d["n"]:.3f} RUB/call; tokens/call pt={d["pt"]/d["n"]:.0f} ct={d["ct"]/d["n"]:.0f}')
