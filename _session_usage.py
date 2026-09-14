# -*- coding: utf-8 -*-
r"""Токены агента по шагам: контекст или рассуждения делают вызовы долгими.

В логе 1056 событий с куском `usage`. Если там есть счётчики токенов, можно увидеть,
растёт ли вход с каждым шагом (тогда долгие вызовы — это обработка большого контекста)
или дело в рассуждениях (тогда долгим был бы выход).

Заодно считается, сколько токенов агент израсходовал за сессию.
"""
import io, json
from collections import defaultdict

LOG = r'D:\models\_session.jsonl'

usage = []
f = io.open(LOG, encoding='utf-8')
for line in f:
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get('type') != 'assistant/chunk':
        continue
    dd = d.get('data') or {}
    ch = dd.get('chunk')
    if not isinstance(ch, dict) or ch.get('type') != 'usage':
        continue
    usage.append({'turn': dd.get('turn'), 'step': dd.get('step'), 'u': ch})
f.close()

print('событий usage: %d' % len(usage))
if usage:
    print('структура первого:')
    u0 = usage[0]['u']
    for k, v in u0.items():
        if k == 'type':
            continue
        print('  %-24s = %r' % (k, v if not isinstance(v, (dict, list)) else type(v).__name__))
    print()
    print('примеры (первые 3):')
    for r in usage[:3]:
        print('  ход %s шаг %s: %s' % (r['turn'], r['step'],
                                       {k: v for k, v in r['u'].items() if k != 'type'}))
print()

# извлекаем счётчики, как бы они ни назывались
keys = set()
for r in usage:
    keys.update(r['u'].keys())
print('все ключи в usage: %s' % sorted(keys))
print()

# ищем поля с токенами
def pick(u, names):
    for n in names:
        if n in u and isinstance(u[n], (int, float)):
            return u[n]
    for k, v in u.items():
        if isinstance(v, dict):
            for n in names:
                if n in v and isinstance(v[n], (int, float)):
                    return v[n]
    return None

rows = []
for r in usage:
    u = r['u']
    rows.append({
        'turn': r['turn'], 'step': r['step'],
        'in': pick(u, ('prompt_tokens', 'input_tokens', 'promptTokens', 'inputTokens')),
        'out': pick(u, ('completion_tokens', 'output_tokens', 'completionTokens', 'outputTokens')),
        'reason': pick(u, ('reasoning_tokens', 'reasoningTokens')),
        'total': pick(u, ('total_tokens', 'totalTokens')),
    })

have = [r for r in rows if r['in'] is not None or r['out'] is not None]
print('шагов со счётчиками: %d из %d' % (len(have), len(rows)))
if have:
    ins = [r['in'] for r in have if r['in'] is not None]
    outs = [r['out'] for r in have if r['out'] is not None]
    reas = [r['reason'] for r in have if r['reason'] is not None]
    if ins:
        ins_s = sorted(ins)
        print('вход: медиана %d, среднее %d, максимум %d, сумма %d (%.1f млн)'
              % (ins_s[len(ins_s) // 2], sum(ins) / len(ins), max(ins), sum(ins),
                 sum(ins) / 1e6))
    if outs:
        outs_s = sorted(outs)
        print('выход: медиана %d, среднее %d, максимум %d, сумма %d (%.1f тыс.)'
              % (outs_s[len(outs_s) // 2], sum(outs) / len(outs), max(outs), sum(outs),
                 sum(outs) / 1e3))
    if reas:
        reas_s = sorted(reas)
        print('рассуждения: медиана %d, среднее %d, максимум %d, сумма %d (%.1f тыс.)'
              % (reas_s[len(reas_s) // 2], sum(reas) / len(reas), max(reas), sum(reas),
                 sum(reas) / 1e3))
        if outs:
            print('доля рассуждений в выходе: %.0f%%' % (100 * sum(reas) / max(sum(outs), 1)))
    print()
    print('=== как менялся вход по ходам (видно ли рост контекста) ===')
    byturn = defaultdict(list)
    for r in have:
        if r['in'] is not None:
            byturn[r['turn']].append(r['in'])
    print('%-6s %8s %10s %10s' % ('ход', 'шагов', 'вход медиана', 'вход максимум'))
    for t in sorted(byturn, key=lambda x: (x is None, x)):
        v = sorted(byturn[t])
        print('%-6s %8d %10d %10d' % (t, len(v), v[len(v) // 2], max(v)))
