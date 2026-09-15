# -*- coding: utf-8 -*-
r"""Три оставшихся потери: что именно и почему.

  1. Рекорд трейд_6мес_2026 / ОДДС — 31 значение (детальные подстроки 4111...4329).
  2. Моторные технологии_6мес_2025 / баланс — 5 значений (затёртый эскалацией столбец).
  3. ИПС_6мес_2025 / баланс — 3 значения кода 1520 (появились после догона).

Для каждого печатаем: какие значения были и какие стали, и что говорит транскрипт страницы.
Ключевой вопрос — потеряны ли ДАННЫЕ или изменилась ФОРМА записи (например, подстроки
свернулись в родительскую строку, или значение переехало в другую колонку).
"""
import io, json, os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

OUT = r'D:\models\extracted'
BAK = os.path.join(OUT, '_backup_v2_before')
CASES = [('Рекорд трейд_6мес_2026', 'cash_flow'),
         ('Моторные технологии_6мес_2025', 'balance'),
         ('ИПС_6мес_2025', 'balance')]


def load(p):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except Exception:
        return None


def items(r, key):
    d = (r or {}).get(key)
    if not d:
        return {}
    return {str(it.get('code')): [('' if v is None else str(v)) for v in (it.get('values') or [])]
            for it in (d.get('items') or []) if it.get('code')}


for stem, key in CASES:
    o, n = load(os.path.join(BAK, stem + '.json')), load(os.path.join(OUT, stem + '.json'))
    oi, ni = items(o, key), items(n, key)
    print('=' * 94)
    print('%s / %s   (было строк %d, стало %d, status %s -> %s)'
          % (stem, key, len(oi), len(ni), o.get('status'), n.get('status')))
    gone = [c for c in oi if c not in ni]
    # свернём пропавшие значения: сумма по колонкам — если она равна родительской строке,
    # данные не потеряны, а свёрнуты в неё
    for c in sorted(gone):
        print('   %-6s было %s' % (c, oi[c]))
    # есть ли в новом артефакте родительская строка с суммой?
    key_codes = {'cash_flow': [('4100', '4110'), ('4200', '4210'), ('4300', '4310'), ('4400', '4410')],
                 'balance': [('1500', '1510')]}.get(key, [])
    for parent, child in key_codes:
        if parent in ni and child in oi:
            print('   родитель %s в новом: %s' % (parent, ni[parent]))
    for w in (n.get('warnings') or [])[:3]:
        print('   предупреждение: %s' % w[:150])
    print()
