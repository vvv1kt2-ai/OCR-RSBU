# -*- coding: utf-8 -*-
r"""Кто стёр первый столбец у Моторных технологий_6мес_2025.

В транскрипте страницы 2 стоит «| Итого по разделу II | 1200 | 459 962 | 481 336 | 377 952 |»,
а в артефакте первый столбец пуст. Значит значение потеряно ПОСЛЕ чтения страницы — либо
структурированием, либо эскалацией. В артефакте есть блок values_ocr1 — значения до эскалации.
Если там 459 962 есть, а в действующих нет, виновата эскалация; если и там пусто — структурирование.
"""
import io, json

P = r'D:\models\extracted\Моторные технологии_6мес_2025.json'
j = json.load(io.open(P, encoding='utf-8'))
bal = j.get('balance') or {}
print('ключи balance: %s' % list(bal))
print()
print('%-6s %-34s %-34s' % ('код', 'действующие values', 'values_ocr1 (до эскалации)'))
for it in (bal.get('items') or []):
    code = str(it.get('code'))
    if code not in ('1200', '1210', '1220', '1230', '1250', '1260', '1100', '1600', '1700'):
        continue
    v = [('' if x is None else str(x)) for x in (it.get('values') or [])]
    v1 = it.get('values_ocr1')
    v1 = [('' if x is None else str(x)) for x in v1] if v1 else None
    print('%-6s %-34s %-34s' % (code, str(v)[:33], str(v1)[:33] if v1 else '—'))
print()
print('предупреждения:')
for w in (j.get('warnings') or []):
    print('   - %s' % w[:200])
