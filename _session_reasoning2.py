# -*- coding: utf-8 -*-
r"""Время рассуждений агента по меткам пакетов `time0`.

`dt` не сходится с длительностью шага (0.19-0.40), значит это не всё время. У пакетов
рассуждений есть `time0` — метка первого куска. По ней считается реальный интервал
рассуждений внутри шага, а он сравнивается с длительностью шага и временем модели.

Заодно проверяется, что именно пишется в текстовые куски ответа.
"""
import io, json
from collections import defaultdict, Counter

LOG = r'D:\models\_session.jsonl'

step_start = {}
step_end = {}
reason_t0 = defaultdict(list)
reason_chars = defaultdict(int)
reason_chunks = defaultdict(int)
chunk_types = Counter()

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
        step_start[key] = d['time']
    elif t == 'step/end' and d.get('time'):
        step_end[key] = d['time']
    elif t == 'reasoning-chunks':
        texts = dd.get('texts') or []
        reason_chars[key] += sum(len(str(x)) for x in texts)
        reason_chunks[key] += len(texts)
        if d.get('time0'):
            reason_t0[key].append(d['time0'])
    elif t == 'assistant/chunk':
        ch = dd.get('chunk')
        if isinstance(ch, dict):
            chunk_types[str(ch.get('type')) + '/' + str(ch.get('blockType'))] += 1
f.close()

print('=== типы кусков ответа ===')
for k, v in chunk_types.most_common(10):
    print('  %-28s %6d' % (k, v))
print()

print('=== рассуждения по меткам пакетов ===')
spans = {}
for key, ts in reason_t0.items():
    if len(ts) >= 2:
        spans[key] = max(ts) - min(ts)
    else:
        spans[key] = 0
tot_span = sum(spans.values())
print('  шагов с рассуждениями: %d' % len(reason_t0))
print('  знаков рассуждений: %d (%.0f тыс.)' % (sum(reason_chars.values()),
                                               sum(reason_chars.values()) / 1000))
print('  кусков: %d' % sum(reason_chunks.values()))
print('  интервал рассуждений суммарно: %.2f ч' % (tot_span / 3600000))
print()

# сравнение с длительностью шага
both = [(k, spans[k], step_end[k] - step_start[k])
        for k in spans if k in step_start and k in step_end and spans[k]]
print('=== доля рассуждений в длительности шага ===')
if both:
    ratios = sorted(s / max(t, 1) for _, s, t in both)
    print('  шагов для сравнения: %d' % len(both))
    print('  доля: медиана %.2f, среднее %.2f, максимум %.2f'
          % (ratios[len(ratios) // 2], sum(ratios) / len(ratios), max(ratios)))
    over = sum(1 for r in ratios if r > 0.8)
    print('  шагов, где рассуждения заняли >80%% шага: %d (%.0f%%)'
          % (over, 100 * over / len(ratios)))
    tot_step = sum(t for _, _, t in both)
    print('  суммарно: рассуждения %.2f ч из %.2f ч этих шагов (%.0f%%)'
          % (tot_span / 3600000, tot_step / 3600000,
             100 * tot_span / max(tot_step, 1)))
print()

print('=== сколько знаков рассуждений на шаг ===')
nz = sorted(v for v in reason_chars.values() if v)
if nz:
    print('  медиана %d, среднее %d, максимум %d' % (nz[len(nz) // 2],
                                                     sum(nz) / len(nz), max(nz)))
    # грубая оценка токенов: знаков на токен
    print('  в токенах (при ~4 знака на токен): медиана ~%d, всего ~%d тыс.'
          % (nz[len(nz) // 2] // 4, sum(nz) / 4 / 1000))
print()
print('=== топ-8 шагов по интервалу рассуждений ===')
for k, s in sorted(spans.items(), key=lambda x: -x[1])[:8]:
    print('  ход %s шаг %s: %.1f с, знаков %d'
          % (k[0], k[1], s / 1000, reason_chars.get(k, 0)))
