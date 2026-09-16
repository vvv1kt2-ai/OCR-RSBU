# -*- coding: utf-8 -*-
r"""Из чего состоит цена эскалации: картинка или вывод?

Вопрос решается логом поставщика. Если у роли esc входные токены почти не зависят от
разрешения (картинка целой страницы считается за ~160 токенов), то снижение dpi до 200
не сэкономит ничего: вся цена — в выходных токенах, то есть в длине расшифровки.

Считает по оплаченному логу plusvibe-usage.ndjson: по каждой модели — число вызовов,
медианы входных и выходных токенов, суммарная цена и её разложение.
"""
import collections
import io
import json
import os
import statistics

LOG = r'D:\models\plusvibe-usage.ndjson'

by_model = collections.defaultdict(list)
with io.open(LOG, encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get('status') != 200:
            continue
        by_model[d.get('model') or '?'].append(d)

print(f'успешных вызовов в логе: {sum(len(v) for v in by_model.values())}')
print()
print(f'{"модель":34} {"выз":>5} {"pt мед":>8} {"ct мед":>8} {"₽ всего":>9} {"₽/выз":>7}')
print('-' * 78)
rows = []
for m, v in sorted(by_model.items(), key=lambda kv: -sum(x['amount_charged_rub'] for x in kv[1])):
    pt = statistics.median(x['prompt_tokens'] for x in v)
    ct = statistics.median(x['completion_tokens'] for x in v)
    tot = sum(x['amount_charged_rub'] for x in v)
    rows.append((m, v, pt, ct, tot))
    print(f'{m[:34]:34} {len(v):5} {pt:8.0f} {ct:8.0f} {tot:9.2f} {tot/len(v):7.4f}')

print()
print('=== вывод: доля входных токенов в цене')
for m, v, pt, ct, tot in rows:
    # цена пропорциональна pt*in + ct*out; берём цены из профиля, но нам важен порядок
    in_tok = sum(x['prompt_tokens'] for x in v)
    out_tok = sum(x['completion_tokens'] for x in v)
    print(f'  {m[:32]:32} вход {in_tok:>9}  выход {out_tok:>9}  '
          f'отношение выход/вход {out_tok/max(in_tok,1):7.1f}')

print()
print('=== если картинка стоит фиксированные ~160 токенов, то размер рендера на цену не влияет')
for m, v, pt, ct, tot in rows:
    if 'anthropic' in m.lower() or m.lower().startswith('anthropic'):
        pts = sorted(x['prompt_tokens'] for x in v)
        print(f'  {m}: входные токены — мин {pts[0]}, медиана {statistics.median(pts):.0f}, '
              f'макс {pts[-1]} при {len(pts)} вызовах')
        # цена на один выходной токен
        per = [x['amount_charged_rub'] / max(x['completion_tokens'], 1) for x in v]
        print(f'      цена за выходной токен: медиана {statistics.median(per)*1e6:.1f} ₽/1M')
