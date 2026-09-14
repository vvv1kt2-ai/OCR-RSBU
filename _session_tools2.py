# -*- coding: utf-8 -*-
r"""Время инструментов (сшивка по ходу и шагу) и разбор повторов модели.

`tool/result` не содержит callId, поэтому инструменты сшиваются с вызовами по паре
(ход, шаг) — в 885 шагах из 1010 инструмент ровно один, так что сшивка однозначна.

Повторы разбираются отдельно: они показывают, сколько времени ушло на транспортные
сбои у поставщика агента.
"""
import io, json
from collections import defaultdict

LOG = r'D:\models\_session.jsonl'

calls = defaultdict(list)
results = defaultdict(list)
retries = []

f = io.open(LOG, encoding='utf-8')
for line in f:
    try:
        d = json.loads(line)
    except Exception:
        continue
    t = d.get('type')
    if not d.get('time'):
        continue
    dd = d.get('data') or {}
    key = (dd.get('turn'), dd.get('step'))
    if t == 'tool/call':
        calls[key].append((dd.get('name'), d['time'], dd.get('arguments')))
    elif t == 'tool/result':
        results[key].append(d['time'])
    elif t == 'llm/retry':
        retries.append(dd)
f.close()

stat = defaultdict(lambda: {'n': 0, 'ms': 0, 'durs': []})
waits = []
for key, lst in calls.items():
    res = sorted(results.get(key) or [])
    for i, (name, t0, args) in enumerate(lst):
        t1 = res[i] if i < len(res) else None
        if t1 is None:
            continue
        dur = t1 - t0
        s = stat[name]
        s['n'] += 1
        s['ms'] += dur
        s['durs'].append(dur)
        if name in ('job_output', 'job_list'):
            waits.append((dur, name, args))

print('=== время по инструментам ===')
print('%-16s %6s %10s %9s %9s %9s'
      % ('инструмент', 'вызовов', 'сумма,ч', 'медиана', 'среднее', 'максимум'))
print('-' * 68)
tot = 0
for name, s in sorted(stat.items(), key=lambda kv: -kv[1]['ms']):
    ds = sorted(s['durs'])
    tot += s['ms']
    print('%-16s %6d %10.2f %8.1fс %8.1fс %8.1fс'
          % (name, s['n'], s['ms'] / 3600000, ds[len(ds) // 2] / 1000,
             s['ms'] / s['n'] / 1000, max(ds) / 1000))
print('-' * 68)
print('%-16s %6d %10.2f' % ('ИТОГО', sum(s['n'] for s in stat.values()), tot / 3600000))
print()

print('=== ожидание фоновой работы (job_output / job_list) ===')
print('вызовов: %d, суммарно %.2f ч' % (len(waits), sum(w[0] for w in waits) / 3600000))
waits.sort(reverse=True)
print('самые долгие:')
for dur, name, args in waits[:10]:
    a = str(args)[:70] if args else ''
    print('  %7.1f с  %-12s %s' % (dur / 1000, name, a))
short = [w for w in waits if w[0] < 60000]
print('коротких (меньше минуты): %d из %d, времени в них %.2f ч'
      % (len(short), len(waits), sum(w[0] for w in short) / 3600000))
print()

print('=== повторы модели (транспортные сбои) ===')
print('событий llm/retry: %d' % len(retries))
byprovider = defaultdict(int)
byfail = defaultdict(int)
byturn = defaultdict(int)
delays = 0
for r in retries:
    byprovider[r.get('provider')] += 1
    f_ = r.get('failure')
    if isinstance(f_, dict):
        byfail[str(f_.get('code'))] += 1
    else:
        byfail[str(f_)[:40]] += 1
    byturn[r.get('turn')] += 1
    try:
        delays += float(r.get('delayMs') or 0)
    except (TypeError, ValueError):
        pass
print('  по поставщику: %s' % dict(byprovider))
print('  по причине:    %s' % dict(byfail))
print('  по ходам:      %s' % dict(sorted(byturn.items())))
print('  сумма пауз между попытками: %.1f с' % (delays / 1000))
print()
print('=== что это значит ===')
print('  поставщик агента — %s' % (list(byprovider.keys())[0] if byprovider else '?'))
print('  сбои: %s' % ', '.join('%s×%d' % (k, v) for k, v in byfail.items()))
