# -*- coding: utf-8 -*-
r"""Итог по логу поставщика: сколько стоила ОБРАБОТКА отчётов и сколько — работа агента.

Разделение по времени (ключ у обоих один, «harness», иначе не разделить):
  окно прогона пилота = 2026-09-15T12 … 16:25 UTC — плотный всплеск, 41 документ за ~4 часа;
  всё остальное      = замеры/проверки 13–14.09 и РАБОТА АГЕНТА DSH (он сам считает на
                       deepseek-v4.1-flash и платит из этого же аккаунта).

Роль определяется по модели: транскрипция/структурирование — gemini-3.8-flash (варианты ag,
ag2, network), эскалация — anthropic (эта среда печатает такие имена пустыми, у них длина 23),
детекция и агент — deepseek-v4.1-flash (не различить иначе как по времени, но у нас метки
детекции лежали в кэше, поэтому в окне прогона deepseek — это почти целиком агент).

Печатаем: сумму по окну прогона (это и есть настоящая цена пилота по данным поставщика),
сумму по остальному и общий итог.
"""
import io, json, collections, datetime

SRC = r'D:\models\plusvibe-usage.ndjson'
WIN_FROM = '2026-09-15T12'
WIN_TO = '2026-09-15T16:30'

MAIN = ('gemini-3.8-flash:ag', 'gemini-3.8-flash:ag2', 'gemini-3.8-flash:network')
DETECT = ('deepseek-v4.1-flash:cxb', 'deepseek-v4.1-flash:cxbc')


def role(m):
    if m in MAIN:
        return 'main'
    if m in DETECT or len(m) in (0, 1):
        return 'detect/agent'
    return 'esc'


win = collections.defaultdict(lambda: {'n': 0, 'rub': 0.0})
out = collections.defaultdict(lambda: {'n': 0, 'rub': 0.0})
win_variant = collections.defaultdict(lambda: {'n': 0, 'rub': 0.0})
statuses = collections.Counter()

with io.open(SRC, encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        ts = r.get('timestamp') or ''
        m = r.get('model') or ''
        rub = float(r.get('amount_charged_rub') or 0)
        bucket = win if WIN_FROM <= ts <= WIN_TO else out
        e = bucket[role(m)]
        e['n'] += 1
        e['rub'] += rub
        if bucket is win and role(m) == 'main':
            v = win_variant[m]
            v['n'] += 1
            v['rub'] += rub
        statuses[r.get('status')] += 1

print('=== ОКНО ПРОГОНА ПИЛОТА (%s … %s UTC)' % (WIN_FROM, WIN_TO))
tot_w = 0.0
for k in ('main', 'esc', 'detect/agent'):
    d = win[k]
    tot_w += d['rub']
    print('  %-13s %5d вызовов %8.2f ₽' % (k, d['n'], d['rub']))
print('  %-13s %5d вызовов %8.2f ₽   <- цена пилота по данным поставщика'
      % ('ИТОГО', sum(win[k]['n'] for k in win), tot_w))
print()
print('  из них транскрипция по вариантам канала:')
for m in sorted(win_variant, key=lambda x: -win_variant[x]['rub']):
    d = win_variant[m]
    print('     %-28s %4d вызовов %7.2f ₽  %6.4f ₽/вызов'
          % (m, d['n'], d['rub'], d['rub'] / max(d['n'], 1)))
print()
print('=== ОСТАЛЬНОЕ (замеры 13–14.09 + работа агента DSH)')
tot_o = 0.0
for k in ('main', 'esc', 'detect/agent'):
    d = out[k]
    tot_o += d['rub']
    print('  %-13s %5d вызовов %8.2f ₽' % (k, d['n'], d['rub']))
print('  %-13s %5d вызовов %8.2f ₽' % ('ИТОГО', sum(out[k]['n'] for k in out), tot_o))
print()
print('=== ВСЕГО ЗА 13–15.09: %.2f ₽' % (tot_w + tot_o))
print('    доля прогона пилота: %.0f%%' % (100 * tot_w / (tot_w + tot_o)))
print()
print('статусы ответов: %s' % dict(sorted(statuses.items())))
