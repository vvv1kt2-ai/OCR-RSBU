# -*- coding: utf-8 -*-
r"""Разбор времени инструментов: какие вызовы съели 5.95 ч.

Считается по каждому инструменту: сколько раз вызван, сколько суммарно занял, медиана
и максимум одного вызова. Отдельно выделяются вызовы, которые только ждали фоновую
работу (`job_output`), — это время, потраченное агентом на ожидание, а не на работу.
"""
import io, json
from collections import defaultdict

LOG = r'D:\models\_session.jsonl'

pending = {}
stat = defaultdict(lambda: {'n': 0, 'ms': 0, 'durs': []})
waits = []
step_tool = defaultdict(int)

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
    if t == 'tool/call':
        cid = dd.get('callId')
        pending[cid] = (dd.get('name'), d['time'], dd.get('arguments'))
        step_tool[(dd.get('turn'), dd.get('step'))] += 1
    elif t == 'tool/result':
        cid = dd.get('callId')
        if cid in pending:
            name, t0, args = pending.pop(cid)
            dur = d['time'] - t0
            s = stat[name]
            s['n'] += 1
            s['ms'] += dur
            s['durs'].append(dur)
            if name in ('job_output', 'job_list'):
                waits.append((dur, t0, name, args))
f.close()

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
print('самые долгие ожидания:')
for dur, t0, name, args in waits[:12]:
    print('  %7.1f с  %s' % (dur / 1000, name))
print()
short = [w for w in waits if w[0] < 60000]
print('коротких ожиданий (меньше минуты): %d из %d — это опрос, а не работа'
      % (len(short), len(waits)))
print('времени в них: %.2f ч' % (sum(w[0] for w in short) / 3600000))
print()

print('=== сколько инструментов на шаг ===')
c = defaultdict(int)
for k, v in step_tool.items():
    c[v] += 1
for k in sorted(c):
    print('  %d инструмент(ов) в шаге: %d шагов' % (k, c[k]))
print()

print('=== повторы модели ===')
print('llm/retry: %d' % sum(1 for _ in ()))
f = io.open(LOG, encoding='utf-8')
retries = []
for line in f:
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get('type') == 'llm/retry':
        dd = d.get('data') or {}
        retries.append({k: str(v)[:70] for k, v in dd.items()})
f.close()
print('  событий: %d' % len(retries))
if retries:
    print('  ключи: %s' % list(retries[0].keys()))
    for r in retries[:6]:
        print('    %s' % r)
