# -*- coding: utf-8 -*-
r"""Сколько агент рассуждает и сколько это стоит по времени.

События `reasoning-chunks` не имеют поля `time`, поэтому оба прошлых замера их
пропустили. У них есть `data.turn`, `data.step`, `data.dt` (длительности порций) и
`data.texts` (сами порции). Это позволяет посчитать и объём рассуждений, и время,
которое они заняли.

Проверяется гипотеза: агент медленный потому, что тоже рассуждает излишне.
"""
import io, json
from collections import defaultdict

LOG = r'D:\models\_session.jsonl'

reason_chars = defaultdict(int)
reason_dt = defaultdict(int)
reason_parts = defaultdict(int)
answer_chars = defaultdict(int)

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
    if t == 'reasoning-chunks':
        texts = dd.get('texts') or []
        dts = dd.get('dt') or []
        reason_chars[key] += sum(len(str(x)) for x in texts)
        reason_parts[key] += len(texts)
        reason_dt[key] += sum(x for x in dts if isinstance(x, int))
    elif t == 'assistant/chunk':
        ch = dd.get('chunk') or {}
        if isinstance(ch, dict):
            if ch.get('blockType') == 'text' and ch.get('type') == 'text-delta':
                answer_chars[key] += len(str(ch.get('text') or ch.get('delta') or ''))
f.close()

tot_r = sum(reason_chars.values())
tot_a = sum(answer_chars.values())
tot_dt = sum(reason_dt.values())

print('=== рассуждения агента за сессию ===')
print('  шагов с рассуждениями: %d' % sum(1 for v in reason_chars.values() if v))
print('  знаков рассуждений:    %d (%.0f тыс.)' % (tot_r, tot_r / 1000))
print('  порций (chunk):        %d' % sum(reason_parts.values()))
print('  знаков ответа:         %d (%.0f тыс.)' % (tot_a, tot_a / 1000))
if tot_r + tot_a:
    print('  доля рассуждений в тексте модели: %.0f%%' % (100 * tot_r / (tot_r + tot_a)))
print()

# проверка единиц dt: сравниваем сумму dt шага с его длительностью
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

step_dur = {}
cur = None
for d in events:
    t = d.get('type')
    dd = d.get('data') or {}
    if t == 'step/start':
        cur = (dd.get('turn'), dd.get('step'), d['time'])
    elif t == 'step/end' and cur:
        step_dur[(cur[0], cur[1])] = d['time'] - cur[2]
        cur = None

print('=== единицы dt (проверка) ===')
pairs = [(reason_dt[k], step_dur[k]) for k in reason_dt if k in step_dur and reason_dt[k]]
pairs.sort(key=lambda p: -p[0])
if pairs:
    print('  шагов с рассуждениями и известной длительностью: %d' % len(pairs))
    print('  сумма dt всех шагов: %d' % tot_dt)
    print('  примеры (сумма dt против длительности шага):')
    for a, b in pairs[:5]:
        print('    dt=%-9d шаг=%-9d отношение %.2f' % (a, b, a / max(b, 1)))
    same = sum(1 for a, b in pairs if 0.5 <= a / max(b, 1) <= 1.5)
    print('  шагов, где dt и длительность одного порядка: %d из %d'
          % (same, len(pairs)))
print()

print('=== время рассуждений по шагам ===')
if tot_dt:
    hrs = tot_dt / 3600000
    print('  если dt в миллисекундах: рассуждения заняли %.2f ч' % hrs)
    print('  для сравнения: всё время модели агента 6.60 ч')
    print('  то есть рассуждения — около %.0f%% времени модели' % (100 * hrs / 6.60))
    ds = sorted(reason_dt.values(), reverse=True)
    print('  топ-10 шагов по времени рассуждений (с):')
    for v in ds[:10]:
        print('    %.1f' % (v / 1000))
    rs = sorted(reason_chars.values(), reverse=True)
    print('  топ-10 шагов по объёму рассуждений (знаков):')
    for v in rs[:10]:
        print('    %d' % v)
    nz = [v for v in reason_chars.values() if v]
    if nz:
        nz.sort()
        print('  на шаг с рассуждениями: медиана %d знаков, среднее %d, максимум %d'
              % (nz[len(nz) // 2], sum(nz) / len(nz), max(nz)))
