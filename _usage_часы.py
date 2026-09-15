# -*- coding: utf-8 -*-
r"""Разделяем расходы по ЧАСАМ: прогон конвейера — это узкий всплеск, работа агента — ровный фон.

Ключ доступа у обоих один («harness»), поэтому разделить иначе нельзя. Но у них разная форма:
  * конвейер — короткий плотный всплеск: 41 документ за ~4 часа, много вызовов транскрипции
    (gemini-3.8-flash) и пачка дорогой эскалации;
  * агент DSH — ровный фон на deepseek-v4.1-flash с огромным чтением из кэша.

Считаем по часам: сколько списано, сколько вызовов и по каким моделям. Печатаем только те
часы, где есть транскрипция/эскалация (признак конвейера), — чтобы отделить его от фона.
"""
import io, json, collections

SRC = r'D:\models\plusvibe-usage.ndjson'

hour_all = collections.defaultdict(lambda: {'n': 0, 'rub': 0.0})
hour_model = collections.defaultdict(lambda: collections.defaultdict(float))
hour_calls = collections.defaultdict(lambda: collections.defaultdict(int))

with io.open(SRC, encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        h = (r.get('timestamp') or '')[:13]
        m = r.get('model') or '?'
        rub = float(r.get('amount_charged_rub') or 0)
        hour_all[h]['n'] += 1
        hour_all[h]['rub'] += rub
        hour_model[h][m] += rub
        hour_calls[h][m] += 1


def short(m):
    """Короткое понятное имя роли; пустые имена эта среда печатает пустыми, поэтому
    подписываем по длине+sha1 (см. память проекта про подмену имён)."""
    table = {
        'deepseek-v4.1-flash:cxb': 'detect?/agent',
        'deepseek-v4.1-flash:cxbc': 'detect?/agent-b',
        'gemini-3.8-flash:ag': 'MAIN:ag',
        'gemini-3.8-flash:ag2': 'MAIN:ag2',
        'gemini-3.8-flash:network': 'MAIN:net',
        '': 'ESC?',
        ':sub5max': 'ESC:sub5max',
        ':network': 'ESC:network',
        ':cxc': 'ESC:cxc',
    }
    return table.get(m, m)


hours = sorted(hour_all)
print('часов в логе: %d, период %s … %s' % (len(hours), hours[0], hours[-1]))
print()
for h in hours:
    d = hour_all[h]
    parts = sorted(hour_model[h].items(), key=lambda kv: -kv[1])
    shown = ', '.join('%s=%.2f(%d)' % (short(m), v, hour_calls[h][m]) for m, v in parts if v > 0)
    print('%s  %7d выз. %7.2f ₽  %s' % (h, d['n'], d['rub'], shown[:120]))
