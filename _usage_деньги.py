# -*- coding: utf-8 -*-
r"""Сколько поставщик списал НА САМОМ ДЕЛЕ — по его собственному полю amount_charged_rub.

Наши цифры (62.65 ₽ за пилот, 116.23 ₽ база) посчитаны по прайсу из providers.json:
цена за 1М токенов × токены. Это наша арифметика, а не факт. Здесь берём то, что plusvibe
записал сам, и сравниваем.

Зачем: имя модели в логе несёт ВАРИАНТ КАНАЛА (gemini-3.8-flash:ag / :ag2 / :network), а в
нашей таблице цен вариант не учтён — мы считаем по базовой цене. Если прогон шёл через
:network, он дороже в 1.25 раза, и наша цена занижена.

Печатаем: сумму списаний по моделям, по дням и общий итог.
"""
import io, json, collections

SRC = r'D:\models\plusvibe-usage.ndjson'

by_model = collections.defaultdict(lambda: {'n': 0, 'rub': 0.0})
by_day = collections.defaultdict(float)
by_day_model = collections.defaultdict(lambda: collections.defaultdict(float))
total = 0.0
zero_charge = 0
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
        rub = float(r.get('amount_charged_rub') or 0)
        m = r.get('model') or '?'
        day = (r.get('timestamp') or '')[:10]
        by_model[m]['n'] += 1
        by_model[m]['rub'] += rub
        by_day[day] += rub
        by_day_model[day][m] += rub
        statuses[r.get('status')] += 1
        total += rub
        if rub == 0:
            zero_charge += 1

print('ИТОГО списано поставщиком: %.2f ₽ за %d вызовов'
      % (total, sum(d['n'] for d in by_model.values())))
print('бесплатных вызовов (списание 0): %d' % zero_charge)
print('статусы: %s' % dict(statuses))
print()
print('%-34s %7s %12s %10s' % ('модель', 'вызовов', 'списано ₽', '₽/вызов'))
for m in sorted(by_model, key=lambda x: -by_model[x]['rub']):
    d = by_model[m]
    print('%-34s %7d %12.2f %10.5f' % (m, d['n'], d['rub'], d['rub'] / max(d['n'], 1)))
print()
print('%-12s %12s   разбивка по моделям' % ('день', 'списано ₽'))
for day in sorted(by_day):
    parts = sorted(by_day_model[day].items(), key=lambda kv: -kv[1])
    shown = ', '.join('%s=%.2f' % (m[-14:], v) for m, v in parts[:3] if v > 0)
    print('%-12s %12.2f   %s' % (day, by_day[day], shown[:90]))
