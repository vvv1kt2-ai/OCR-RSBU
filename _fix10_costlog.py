# -*- coding: utf-8 -*-
r"""Цена вызова детекции по видам: постраничная против групповой.

Разбирает лог замера (`_fix10_reps.log`) — строки вида
  [llm] <модель> pt=<вход> ct=<выход> cost=... finish=... <сек>s
и считает цену по таблице цен активного профиля, отдельно для вызовов режима A (группы)
и режима B (по одной странице).
"""
import io, re, sys, collections

sys.path.insert(0, r'D:\models')
import pipeline as P

LOG = sys.argv[1] if len(sys.argv) > 1 else r'D:\models\_fix10_reps.log'
LINE = re.compile(r'\[llm\]\s+(\S+)\s+pt=(\d+)\s+ct=(\d+)')


def read_log(path):
    r"""Прочитать лог, написанный перенаправлением PowerShell.

    `*>` в этой среде пишет UTF-16LE с BOM (байты ff fe), а не UTF-8, поэтому чтение
    «как обычно» даёт мусор и ноль найденных вызовов вместо ошибки — молчаливый
    результат, из-за которого можно решить, что вызовов не было вовсе.
    """
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-16', 'cp1251'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')



detect_model = P.ACTIVE_PROFILE.roles['detect']
pr = P.PRICES.get(detect_model)
print('модель детекции: %s, цена %s ₽ за 1M' % (detect_model, pr))
print('лог: %s' % LOG)
print()

lines = [l for l in read_log(LOG).splitlines() if '[llm]' in l]
print('строк с вызовами: %d' % len(lines))

# в логе вызовы идут подряд, разделённые отметками режимов; привязываем по порядку:
# сначала все вызовы прогонов режима A, затем режима B — но надёжнее считать по pt:
# групповой вызов несёт несколько изображений, поэтому pt заметно больше.
costs = collections.Counter()
counts = collections.Counter()
toks = collections.defaultdict(lambda: [0, 0])
for l in lines:
    m = LINE.search(l)
    if not m:
        continue
    model, pt, ct = m.group(1), int(m.group(2)), int(m.group(3))
    if model != detect_model or not pr:
        continue
    rub = (pt * pr[0] + ct * pr[1]) / 1e6
    kind = 'группа (несколько страниц)' if pt > 1500 else 'одна страница'
    costs[kind] += rub
    counts[kind] += 1
    toks[kind][0] += pt
    toks[kind][1] += ct

print()
print('%-28s %8s %10s %10s %12s' % ('вид вызова', 'вызовов', 'вход/выз', 'выход/выз', 'всего ₽'))
for k in sorted(counts, key=lambda x: -counts[x]):
    n = counts[k]
    print('%-28s %8d %10.0f %10.0f %12.4f'
          % (k, n, toks[k][0] / n, toks[k][1] / n, costs[k]))
print()
per_page = None
for k in counts:
    if k == 'одна страница':
        per_page = costs[k] / counts[k]
if per_page:
    print('цена вызова по одной странице: %.5f ₽' % per_page)
    print('ПРОЕКЦИЯ на корпус 5884 страницы: %.1f ₽' % (per_page * 5884))
    print('  (это 1 вызов на страницу; при бюджете 300 ₽ — %.0f%% бюджета)'
          % (100.0 * per_page * 5884 / 300))
else:
    print('вызовов по одной странице в логе не найдено')
