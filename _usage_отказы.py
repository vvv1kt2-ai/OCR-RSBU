# -*- coding: utf-8 -*-
r"""Таймауты и ошибки поставщика по его собственному логу: кто виноват и платим ли мы за отказы.

Жалоба: «частые таймауты». Проверяем по данным поставщика (plusvibe-usage.ndjson), а не по
ощущению. В записи есть status, latency_ms и amount_charged_rub — значит можно ответить:

  1. сколько отказов и каких (502/503/504 — это таймауты инфраструктуры, 499 — мы сами оборвали);
  2. списывают ли деньги за отказ (если да, это прямая потеря: платим за пустоту);
  3. какова задержка по ролям: p50/p90/max, и не упирается ли она в наш собственный предел.

Роли: main — gemini-3.8-flash (транскрипция/структурирование), esc — anthropic (у этой среды
имена пустые, опознаём по длине), detect — deepseek-v4.1-flash.

Печатаем только сводку.
"""
import io, json, collections

SRC = r'D:\models\plusvibe-usage.ndjson'
MAIN_PREFIX = 'gemini-3.8-flash'
DETECT_PREFIX = 'deepseek-v4.1-flash'


def role(m):
    if m.startswith(MAIN_PREFIX):
        return 'main'
    if m.startswith(DETECT_PREFIX):
        return 'detect'
    return 'esc'


st = collections.defaultdict(lambda: collections.Counter())
charged = collections.defaultdict(lambda: collections.defaultdict(float))
lat = collections.defaultdict(lambda: collections.defaultdict(list))

with io.open(SRC, encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        k = role(r.get('model') or '')
        s = r.get('status')
        st[k][s] += 1
        charged[k][s] += float(r.get('amount_charged_rub') or 0)
        ms = r.get('latency_ms')
        if ms is not None:
            lat[k][s].append(int(ms))


def pct(v, p):
    if not v:
        return 0
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p / 100.0))]


print('=== отказы и списания по ролям')
for k in ('main', 'esc', 'detect'):
    tot = sum(st[k].values())
    if not tot:
        continue
    print('  %s: всего %d вызовов' % (k, tot))
    for s in sorted(st[k], key=lambda x: -st[k][x]):
        n = st[k][s]
        rub = charged[k][s]
        mark = 'списано' if rub > 0 else 'бесплатно'
        print('      статус %-4s %7d (%5.2f%%)  %8.2f ₽  %s  %5.2f ₽/вызов'
              % (s, n, 100.0 * n / tot, rub, mark, rub / n))
    print()

print('=== задержка, мс (только успешные ответы 200)')
print('  %-8s %10s %8s %8s %9s' % ('роль', 'запросов', 'p50', 'p90', 'max'))
for k in ('main', 'esc', 'detect'):
    v = lat[k][200]
    if not v:
        continue
    print('  %-8s %10d %8d %8d %9d' % (k, len(v), pct(v, 50), pct(v, 90), max(v)))
print()

print('=== задержка на отказах (не 200): сколько ждём впустую')
for k in ('main', 'esc', 'detect'):
    for s in sorted(st[k]):
        if s == 200:
            continue
        v = lat[k][s]
        if not v:
            continue
        print('  %-8s статус %-4s %6d отказов, p50 %6d мс, max %7d мс'
              % (k, s, len(v), pct(v, 50), max(v)))
billed_fails = sum(charged[k][s] for k in charged for s in charged[k] if s != 200)
print()
print('ИТОГО списано за НЕуспешные вызовы: %.2f ₽' % billed_fails)
