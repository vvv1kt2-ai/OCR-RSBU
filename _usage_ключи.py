# -*- coding: utf-8 -*-
r"""Лог поставщика смешивает ДВА источника расходов — разделяем их по полю api_key.

В первой строке файла стоит `"api_key":"harness"`. Это подозрительно: у нашего конвейера ключ
берётся из credentials (PLUSVIBE_API_KEY), а «harness» — имя агента DSH, то есть это расходы
САМОЙ ЭТОЙ СЕССИИ, а не обработки отчётов. Если их сложить, получится бессмысленная цифра:
15975 вызовов deepseek-v4.1-flash при 264 вызовах нашего прогона.

Поэтому считаем раздельно по api_key и по ролям (роль определяется по имени модели, а имя
модели эта среда печатает ПУСТЫМ — см. память проекта, поэтому опираемся на то, что в файле
имя всё же лежит целиком, и печатаем его длину и sha1, а не глазами).

Печатаем: списания по ключу, внутри ключа — по модели, и период.
"""
import io, json, hashlib, collections

SRC = r'D:\models\plusvibe-usage.ndjson'

by_key = collections.defaultdict(lambda: {'n': 0, 'rub': 0.0})
by_key_model = collections.defaultdict(lambda: collections.defaultdict(lambda: {'n': 0, 'rub': 0.0}))
model_facts = {}
key_days = collections.defaultdict(lambda: collections.defaultdict(float))

with io.open(SRC, encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        k = r.get('api_key') or '?'
        m = r.get('model') or '?'
        rub = float(r.get('amount_charged_rub') or 0)
        by_key[k]['n'] += 1
        by_key[k]['rub'] += rub
        e = by_key_model[k][m]
        e['n'] += 1
        e['rub'] += rub
        model_facts[m] = (len(m), hashlib.sha1(m.encode('utf-8')).hexdigest()[:8])
        key_days[k][(r.get('timestamp') or '')[:10]] += rub

print('=== по ключу доступа (кто платил)')
for k in sorted(by_key, key=lambda x: -by_key[x]['rub']):
    d = by_key[k]
    days = ', '.join('%s=%.2f' % (x, key_days[k][x]) for x in sorted(key_days[k]))
    print('  %-12s %6d вызовов  %8.2f ₽   дни: %s' % (k, d['n'], d['rub'], days))
print()
for k in sorted(by_key, key=lambda x: -by_key[x]['rub']):
    print('=== ключ «%s»: разбивка по моделям' % k)
    for m in sorted(by_key_model[k], key=lambda x: -by_key_model[k][x]['rub']):
        e = by_key_model[k][m]
        ln, h = model_facts[m]
        print('  %-26s %6d вызовов %8.2f ₽  %8.5f ₽/вызов  (длина имени %d, sha1 %s)'
              % ('<пусто>' if not m else m, e['n'], e['rub'], e['rub'] / max(e['n'], 1), ln, h))
    print()
