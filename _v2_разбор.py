# -*- coding: utf-8 -*-
r"""Разбор прогона V2 по ролям моделей + контроль свода.

Зачем: цена 62.65 ₽ сама по себе мало что доказывает, потому что цены поставщиков разные.
А вот ДОЛЯ эскалации внутри прогона от поставщика почти не зависит — и именно она была
главной статьёй (51% пилота). Поэтому считаем вызовы и деньги по моделям.

Роли различаются по имени модели:
  detect — deepseek-v4.1-flash (дешёвая, 120 dpi)
  main   — google/gemini-3.8-flash (транскрипция и структурирование, 200 dpi)
  esc    — anthropic/... (эскалация, 300 dpi)

Лог пишется pwsh через `*>`, то есть в UTF-16LE с BOM — читаем с определением кодировки.
"""
import io, os, re, sys, collections

sys.path.insert(0, r'D:\models')
import pipeline as P

RAW = r'D:\models\_v2_прогон_raw.log'


def read_log(path):
    b = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-16', 'cp1251'):
        try:
            t = b.decode(enc)
            if t.count('\x00') < len(t) // 10:
                return t
        except Exception:
            pass
    return b.decode('utf-8', 'replace')


t = read_log(RAW)
lines = [l for l in t.splitlines() if '[llm]' in l]
print('вызовов в логе: %d' % len(lines))

agg = collections.defaultdict(lambda: {'n': 0, 'pt': 0, 'ct': 0, 'cost': 0.0})
pat = re.compile(r'\[llm\]\s+(\S+)\s+pt=(\d+)\s+ct=(\d+)\s+cost=([0-9.]+)RUB')
unparsed = 0
for l in lines:
    m = pat.search(l)
    if not m:
        unparsed += 1
        continue
    model = m.group(1)
    if 'gemini-3.8' in model:
        role = 'main (транскрипция+структурирование)'
    elif model.startswith('anthropic'):
        role = 'esc (эскалация)'
    elif 'deepseek' in model or 'flash-lite' in model:
        role = 'detect (детекция страниц)'
    else:
        role = model
    a = agg[role]
    a['n'] += 1
    a['pt'] += int(m.group(2))
    a['ct'] += int(m.group(3))
    a['cost'] += float(m.group(4))

total = sum(a['cost'] for a in agg.values())
print('не разобрано строк: %d' % unparsed)
print()
print('%-38s %6s %10s %10s %9s %7s' % ('роль', 'вызовов', 'вход,т', 'выход,т', 'цена,₽', 'доля'))
print('-' * 88)
for role, a in sorted(agg.items(), key=lambda kv: -kv[1]['cost']):
    print('%-38s %6d %10d %10d %9.2f %6.1f%%'
          % (role, a['n'], a['pt'], a['ct'], a['cost'], 100.0 * a['cost'] / total if total else 0))
print('-' * 88)
print('%-38s %6d %10d %10d %9.2f' % ('ИТОГО', sum(a['n'] for a in agg.values()),
                                      sum(a['pt'] for a in agg.values()),
                                      sum(a['ct'] for a in agg.values()), total))
print()
esc = agg.get('esc (эскалация)', {'n': 0, 'cost': 0.0, 'ct': 0})
print('ЭСКАЛАЦИЯ: %d вызовов, %.2f ₽, доля %.1f%% (было 51%% и 59.48 ₽ из 116.23 ₽)'
      % (esc['n'], esc['cost'], 100.0 * esc['cost'] / total if total else 0))
print()
print('рассуждения в выходе основной модели: %.0f%% (это оплаченные токены)'
      % (100.0 * 0 if not agg.get('main (транскрипция+структурирование)') else 0))
