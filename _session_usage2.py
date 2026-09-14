# -*- coding: utf-8 -*-
r"""Решающая проверка: что делает вызовы агента долгими — контекст или рассуждения.

В `usage` есть `inputTokens`, `outputTokens` и `cacheReadTokens`. Полный вход шага —
это `inputTokens + cacheReadTokens`. Провайдер PlusVibe токены рассуждений не сообщает
вовсе (в каталоге `reasoningShare: null`), поэтому о рассуждениях судим по потоку.

Здесь шаги раскладываются по размеру входа и для каждой группы считается время модели.
Если время растёт вместе с входом — виноват контекст, а не рассуждения.
"""
import io, json
from collections import defaultdict

LOG = r'D:\models\_session.jsonl'
sys_path = r'D:\models'

usage = {}
steps = {}
cur = None
open_tool = None
f = io.open(LOG, encoding='utf-8')
for line in f:
    try:
        d = json.loads(line)
    except Exception:
        continue
    t = d.get('type')
    dd = d.get('data') or {}
    if not isinstance(dd, dict):
        continue
    key = (dd.get('turn'), dd.get('step'))
    if t == 'step/start' and d.get('time'):
        cur = {'key': key, 'start': d['time'], 'tool_ms': 0, 'tools': 0}
        steps[key] = cur
    elif t == 'tool/call':
        open_tool = d.get('time')
    elif t == 'tool/result' and cur is not None and open_tool:
        cur['tool_ms'] += d['time'] - open_tool
        cur['tools'] += 1
        open_tool = None
    elif t == 'step/end' and cur is not None:
        cur['end'] = d['time']
        cur = None
    elif t == 'assistant/chunk':
        ch = dd.get('chunk')
        if isinstance(ch, dict) and ch.get('type') == 'usage':
            u = ch.get('usage') or {}
            usage[key] = u
f.close()

rows = []
for key, u in usage.items():
    s = steps.get(key)
    if not s or 'end' not in s:
        continue
    prompt = (u.get('inputTokens') or 0) + (u.get('cacheReadTokens') or 0)
    out = u.get('outputTokens') or 0
    model_ms = (s['end'] - s['start']) - s['tool_ms']
    rows.append({'turn': key[0], 'step': key[1], 'prompt': prompt, 'out': out,
                 'cache': u.get('cacheReadTokens') or 0, 'model_ms': model_ms})

print('шагов с полными данными: %d' % len(rows))
pr = sorted(r['prompt'] for r in rows)
ou = sorted(r['out'] for r in rows)
print('вход (input+cacheRead): медиана %d, среднее %d, максимум %d'
      % (pr[len(pr) // 2], sum(pr) / len(pr), max(pr)))
print('выход: медиана %d, среднее %d, максимум %d'
      % (ou[len(ou) // 2], sum(ou) / len(ou), max(ou)))
print('сумма входа: %.1f млн токенов, сумма выхода: %.1f тыс.'
      % (sum(pr) / 1e6, sum(ou) / 1e3))
print('сумма времени модели: %.2f ч' % (sum(r['model_ms'] for r in rows) / 3600000))
print()

print('=== время вызова в зависимости от размера входа ===')
BUCKETS = [(0, 10000, 'до 10 тыс.'), (10000, 30000, '10-30 тыс.'),
           (30000, 60000, '30-60 тыс.'), (60000, 120000, '60-120 тыс.'),
           (120000, 10 ** 9, 'больше 120 тыс.')]
print('%-16s %7s %12s %12s %10s' % ('вход', 'шагов', 'медиана,с', 'среднее,с', 'доля шагов'))
print('-' * 62)
for lo, hi, label in BUCKETS:
    grp = [r['model_ms'] for r in rows if lo <= r['prompt'] < hi]
    if not grp:
        print('%-16s %7d %12s %12s %10s' % (label, 0, '—', '—', '—'))
        continue
    g = sorted(grp)
    print('%-16s %7d %12.1f %12.1f %9.0f%%'
          % (label, len(g), g[len(g) // 2] / 1000, sum(g) / len(g) / 1000,
             100 * len(g) / len(rows)))
print('-' * 62)
print()

print('=== доля времени модели по размеру входа ===')
tot = sum(r['model_ms'] for r in rows)
for lo, hi, label in BUCKETS:
    grp = [r['model_ms'] for r in rows if lo <= r['prompt'] < hi]
    if grp:
        print('  %-16s %6.2f ч (%.0f%% времени модели), шагов %d'
              % (label, sum(grp) / 3600000, 100 * sum(grp) / tot, len(grp)))
print()

print('=== кэш ===')
cached = [r for r in rows if r['cache']]
print('шагов с кэшированным префиксом: %d из %d' % (len(cached), len(rows)))
if cached:
    ratio = sorted(r['cache'] / max(r['prompt'], 1) for r in cached)
    print('  доля кэша во входе: медиана %.0f%%' % (100 * ratio[len(ratio) // 2]))
big = [r for r in rows if r['prompt'] > 120000]
print('  шагов с входом больше 120 тыс.: %d' % len(big))
if big:
    print('  их суммарное время: %.2f ч (%.0f%% всего времени модели)'
          % (sum(r['model_ms'] for r in big) / 3600000,
             100 * sum(r['model_ms'] for r in big) / tot))
    print('  средний выход у них: %.0f токенов' % (sum(r['out'] for r in big) / len(big)))
    print('  время на шаг: медиана %.1f с' % (sorted(r['model_ms'] for r in big)[len(big) // 2] / 1000))
print()
print('=== вывод ===')
small = [r['model_ms'] for r in rows if r['prompt'] < 10000]
bigms = [r['model_ms'] for r in rows if r['prompt'] > 120000]
if small and bigms:
    print('  мелкий вход: медиана %.1f с;  большой вход: медиана %.1f с;  разница %.1f раза'
          % (sorted(small)[len(small) // 2] / 1000,
             sorted(bigms)[len(bigms) // 2] / 1000,
             (sorted(bigms)[len(bigms) // 2]) / max(sorted(small)[len(small) // 2], 1)))

json.dump({'rows': len(rows), 'prompt_median': pr[len(pr) // 2],
           'prompt_max': max(pr), 'prompt_sum': sum(pr), 'out_sum': sum(ou),
           'model_hours': tot / 3600000},
          io.open(r'D:\models\_session_usage.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('-> _session_usage.json')
