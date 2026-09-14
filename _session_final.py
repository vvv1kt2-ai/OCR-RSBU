# -*- coding: utf-8 -*-
r"""Итоговая таблица: по каждому ходу — шаги, время модели, инструменты, ожидание фонов.

Сводит вместе всё, что найдено: число вызовов модели, их длительность, время
инструментов и отдельно время, потраченное на ожидание фоновой работы (`job_output`),
а также размер входа на шаг.
"""
import io, json
from collections import defaultdict

LOG = r'D:\models\_session.jsonl'

turns = {}
cur = None
open_tool = None
toolname = None
usage = {}

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
    tr = dd.get('turn')
    if t == 'turn/start':
        cur = {'n': tr, 'start': d['time'], 'end': None, 'steps': 0, 'tool_ms': 0,
               'job_ms': 0, 'model_ms': 0, 'prompt': 0, 'out': 0, 'step_start': None}
        turns[tr] = cur
    elif t == 'turn/end' and cur is not None:
        cur['end'] = d['time']
        cur = None
    elif cur is None:
        continue
    elif t == 'step/start':
        cur['steps'] += 1
        cur['step_start'] = d['time']
    elif t == 'step/end':
        if cur['step_start']:
            cur['model_ms'] += (d['time'] - cur['step_start']) - cur.get('last_tool_ms', 0)
        cur['step_start'] = None
        cur['last_tool_ms'] = 0
    elif t == 'tool/call':
        open_tool = d['time']
        toolname = dd.get('name')
    elif t == 'tool/result' and open_tool:
        dur = d['time'] - open_tool
        cur['tool_ms'] += dur
        cur['last_tool_ms'] = cur.get('last_tool_ms', 0) + dur
        if toolname in ('job_output', 'job_list'):
            cur['job_ms'] += dur
        open_tool = None
    elif t == 'assistant/chunk':
        ch = dd.get('chunk')
        if isinstance(ch, dict) and ch.get('type') == 'usage':
            u = ch.get('usage') or {}
            cur['prompt'] += (u.get('inputTokens') or 0) + (u.get('cacheReadTokens') or 0)
            cur['out'] += u.get('outputTokens') or 0
f.close()

last = max(d['time'] for d in [{'time': 0}]) if False else None
print('%-4s %-16s %8s %8s %9s %9s %9s %8s'
      % ('ход', 'длит', 'шагов', 'модель,ч', 'инстр,ч', 'ожид,ч', 'вход,млн', 'выход,тыс'))
print('-' * 84)
tot = defaultdict(float)
for n in sorted(turns):
    t = turns[n]
    dur = (t['end'] - t['start']) if t['end'] else 0
    tot['dur'] += dur
    tot['steps'] += t['steps']
    tot['model'] += t['model_ms']
    tot['tool'] += t['tool_ms']
    tot['job'] += t['job_ms']
    tot['prompt'] += t['prompt']
    tot['out'] += t['out']
    print('%-4d %8.2f ч %8d %8.2f %9.2f %9.2f %9.1f %8.1f'
          % (n, dur / 3600000, t['steps'], t['model_ms'] / 3600000,
             t['tool_ms'] / 3600000, t['job_ms'] / 3600000,
             t['prompt'] / 1e6, t['out'] / 1e3))
print('-' * 84)
print('%-4s %8.2f ч %8d %8.2f %9.2f %9.2f %9.1f %8.1f'
      % ('ВСЕГО', tot['dur'] / 3600000, int(tot['steps']), tot['model'] / 3600000,
         tot['tool'] / 3600000, tot['job'] / 3600000, tot['prompt'] / 1e6,
         tot['out'] / 1e3))
print()
print('=== доля ожидания фоновой работы во времени инструментов ===')
if tot['tool']:
    print('  инструменты: %.2f ч, из них ожидание job_output: %.2f ч (%.0f%%)'
          % (tot['tool'] / 3600000, tot['job'] / 3600000,
             100 * tot['job'] / tot['tool']))
print()
print('=== среднее на один вызов модели ===')
if tot['steps']:
    print('  шагов: %d, время модели: %.2f ч, среднее %.1f с на вызов'
          % (tot['steps'], tot['model'] / 3600000, tot['model'] / tot['steps'] / 1000))
    print('  вход на вызов: %.0f тыс. токенов (медиана по всем шагам — 129 тыс.)'
          % (tot['prompt'] / tot['steps'] / 1000))
    print('  выход на вызов: %.0f токенов' % (tot['out'] / tot['steps']))
