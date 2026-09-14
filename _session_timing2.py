# -*- coding: utf-8 -*-
r"""Второй разбор: отделить время модели агента от времени инструментов.

Первый замер был неверен: `step/end` закрывается ПОСЛЕ инструментов шага, поэтому
время шага включало и работу скриптов. Здесь время модели считается как время шага
минус длительность инструментов внутри него.

Отдельно измеряется объём рассуждений агента (события `reasoning-chunks`) — чтобы
проверить гипотезу «агент тоже рассуждает излишне».
"""
import io, json, datetime
from collections import Counter

LOG = r'D:\models\_session.jsonl'


def fmt(ms):
    return datetime.datetime.fromtimestamp(ms / 1000).strftime('%d.%m %H:%M:%S')


events = []
f = io.open(LOG, encoding='utf-8')
for line in f:
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get('time'):
        events.append(d)
f.close()
events.sort(key=lambda d: d['time'])

print('=== все типы событий ===')
c = Counter(d.get('type') for d in events)
for k, v in c.most_common():
    print('  %-34s %6d' % (k, v))
print()

# структура события рассуждений
for d in events:
    if d.get('type') == 'reasoning-chunks':
        dd = d.get('data') or {}
        print('reasoning-chunks ключи: %s' % list(dd.keys()))
        for k, v in dd.items():
            if isinstance(v, list):
                print('  %s: list[%d], первый элемент %s'
                      % (k, len(v), type(v[0]).__name__ if v else '—'))
            elif isinstance(v, str):
                print('  %s: str[%d]' % (k, len(v)))
            else:
                print('  %s = %r' % (k, v))
        break
print()

# --- шаги: время модели отдельно от инструментов ---
steps = []
cur = None
open_tool = None
for d in events:
    t = d.get('type')
    if t == 'step/start':
        cur = {'start': d['time'], 'tool_ms': 0, 'tools': 0, 'reason_chars': 0,
               'text_chars': 0, 'turn': (d.get('data') or {}).get('turn')}
        steps.append(cur)
    elif t == 'tool/call':
        open_tool = d['time']
    elif t == 'tool/result':
        if cur is not None and open_tool:
            cur['tool_ms'] += d['time'] - open_tool
            cur['tools'] += 1
            open_tool = None
    elif t == 'step/end' and cur is not None:
        cur['end'] = d['time']
        cur = None
    elif t == 'reasoning-chunks' and cur is not None:
        dd = d.get('data') or {}
        for k, v in dd.items():
            if isinstance(v, list):
                cur['reason_chars'] += sum(len(str(x)) for x in v)
            elif isinstance(v, str):
                cur['reason_chars'] += len(v)
    elif t in ('text-chunks', 'assistant/chunk') and cur is not None:
        dd = d.get('data') or {}
        for k, v in dd.items():
            if isinstance(v, list):
                cur['text_chars'] += sum(len(str(x)) for x in v)
            elif isinstance(v, str):
                cur['text_chars'] += len(v)

done = [s for s in steps if s.get('end')]
print('=== шаги ===')
print('шагов всего: %d, завершённых: %d' % (len(steps), len(done)))
model_ms = sum((s['end'] - s['start']) - s['tool_ms'] for s in done)
tool_ms = sum(s['tool_ms'] for s in done)
span_ms = sum(s['end'] - s['start'] for s in done)
print('  сумма времени шагов:        %6.2f ч' % (span_ms / 3600000))
print('  из них модель агента:       %6.2f ч (%.0f%%)'
      % (model_ms / 3600000, 100 * model_ms / max(span_ms, 1)))
print('  из них инструменты:         %6.2f ч (%.0f%%)'
      % (tool_ms / 3600000, 100 * tool_ms / max(span_ms, 1)))
print()
m = sorted((s['end'] - s['start']) - s['tool_ms'] for s in done)
print('время одного вызова модели агента (без инструментов):')
print('  медиана %.1f с, среднее %.1f с, максимум %.1f с'
      % (m[len(m) // 2] / 1000, sum(m) / len(m) / 1000, max(m) / 1000))
for thr in (10, 30, 60, 120):
    n = sum(1 for x in m if x > thr * 1000)
    print('  дольше %3d с: %4d шагов (%.0f%%), суммарно %.2f ч'
          % (thr, n, 100 * n / len(m), sum(x for x in m if x > thr * 1000) / 3600000))
print()

# --- шаги без инструментов = чистый вызов модели ---
pure = [(s['end'] - s['start']) for s in done if s['tools'] == 0]
witht = [(s['end'] - s['start']) - s['tool_ms'] for s in done if s['tools'] > 0]
print('=== шаги без вызова инструментов (чистый ответ модели) ===')
if pure:
    ps = sorted(pure)
    print('  таких шагов: %d из %d (%.0f%%)'
          % (len(pure), len(done), 100 * len(pure) / len(done)))
    print('  медиана %.1f с, среднее %.1f с, максимум %.1f с'
          % (ps[len(ps) // 2] / 1000, sum(ps) / len(ps) / 1000, max(ps) / 1000))
    print('  суммарно %.2f ч' % (sum(ps) / 3600000))
if witht:
    ws = sorted(witht)
    print('  шаги с инструментами: %d, время модели в них: медиана %.1f с, суммарно %.2f ч'
          % (len(witht), ws[len(ws) // 2] / 1000, sum(witht) / 3600000))
print()

# --- рассуждения агента ---
print('=== рассуждения агента ===')
rc = [s['reason_chars'] for s in done]
tc = [s['text_chars'] for s in done]
print('  шагов с рассуждениями: %d из %d (%.0f%%)'
      % (sum(1 for x in rc if x > 0), len(done), 100 * sum(1 for x in rc if x > 0) / len(done)))
print('  знаков рассуждений всего: %d (%.0f тыс.)' % (sum(rc), sum(rc) / 1000))
print('  знаков ответа всего:      %d (%.0f тыс.)' % (sum(tc), sum(tc) / 1000))
if sum(rc):
    print('  доля рассуждений: %.0f%% от всего текста модели'
          % (100 * sum(rc) / max(sum(rc) + sum(tc), 1)))
    rcs = sorted(rc)
    print('  на шаг: медиана %d знаков, среднее %d, максимум %d'
          % (rcs[len(rcs) // 2], sum(rc) / len(rc), max(rc)))
print()
print('  для сравнения: модель детекции PlusVibe тратит 200-1900 токенов рассуждений')
print('  на один вызов по 8 страницам; здесь измерены знаки, не токены, но порядок виден.')
