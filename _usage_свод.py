# -*- coding: utf-8 -*-
r"""Свод по логу поставщика plusvibe-usage.ndjson — независимая проверка нашей цены.

Наши 62.65 ₽ посчитаны по прайсу из providers.json (цена за 1М токенов). Лог поставщика —
это то, что он записал САМ. Если сходится, наша методика верна; если нет, значит мы считаем
не то, что платим.

Отдельный повод для беспокойства: имя модели в логе несёт вариант канала (в первой строке
«gemini-3.8-flash:ag2»). У plusvibe варианты Ag / Ag2 / Network / Cxc стоят по-разному,
поэтому надо убедиться, что мы платим по тому варианту, который думаем.

Печатаем только сводку: ключи, период, разбивку по моделям и суммарные токены.
"""
import io, json, collections

SRC = r'D:\models\plusvibe-usage.ndjson'

keys = collections.Counter()
by_model = collections.defaultdict(lambda: {'n': 0, 'pt': 0, 'ct': 0, 'cache': 0})
ts_first = ts_last = None
bad = 0

with io.open(SRC, encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            bad += 1
            continue
        for k in r:
            keys[k] += 1
        m = r.get('model') or '?'
        d = by_model[m]
        d['n'] += 1
        d['pt'] += int(r.get('prompt_tokens') or 0)
        d['ct'] += int(r.get('completion_tokens') or 0)
        d['cache'] += int(r.get('cache_read_tokens') or 0)
        ts = r.get('timestamp')
        if ts:
            if ts_first is None or ts < ts_first:
                ts_first = ts
            if ts_last is None or ts > ts_last:
                ts_last = ts

print('строк разобрано: %d, битых: %d' % (sum(d['n'] for d in by_model.values()), bad))
print('период: %s … %s' % (ts_first, ts_last))
print()
print('ключи в записи: %s' % ', '.join(sorted(keys)))
print()
print('%-34s %7s %12s %12s %12s' % ('модель', 'вызовов', 'вход токенов', 'выход токенов', 'кэш-чтение'))
for m in sorted(by_model, key=lambda x: -by_model[x]['n']):
    d = by_model[m]
    print('%-34s %7d %12s %12s %12s'
          % (m, d['n'], format(d['pt'], ','), format(d['ct'], ','), format(d['cache'], ',')))
print()
tp = sum(d['pt'] for d in by_model.values())
tc = sum(d['ct'] for d in by_model.values())
print('ИТОГО: %s вызовов, вход %s, выход %s' % (format(sum(d['n'] for d in by_model.values()), ','),
                                               format(tp, ','), format(tc, ',')))
