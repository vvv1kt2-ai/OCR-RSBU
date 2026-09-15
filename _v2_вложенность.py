# -*- coding: utf-8 -*-
r"""Проверка собственного инструмента: не потеряны ли значения «Рекорд трейд» на самом деле?

Тест дал 57 -> 57 заполненных ячеек, хотя строк 42 -> 13. Значит детализация, скорее всего, не
исчезла, а ПЕРЕЕХАЛА во вложенные строки (children), а моё сравнение `_v2_итог_финал.py` читает
только верхний уровень items и вложенное не видит. Тогда «31 потерянное значение» — дефект моего
измерителя, а не потери данных, и это ровно тот урок, что уже записан в память проекта:
прежде чем объявлять потерю, проверить сам инструмент.

Здесь считаем заполненные значения по уровням: верхний уровень, вложенные, и полный обход.
"""
import io, json, os

OUT = r'D:\models\extracted'
BAK = os.path.join(OUT, '_backup_v2_before')
STEM, KEY = 'Рекорд трейд_6мес_2026', 'cash_flow'


def walk(items, depth=0):
    """Полный обход с учётом вложенных строк."""
    out = []
    for it in items or []:
        out.append((depth, str(it.get('code')), [('' if v is None else str(v)) for v in (it.get('values') or [])]))
        out.extend(walk(it.get('children'), depth + 1))
    return out


def filled(items):
    n = 0
    for _, _, vals in walk(items):
        n += sum(1 for v in vals if v != '')
    return n


for tag, path in (('БЭКАП', os.path.join(BAK, STEM + '.json')),
                  ('НОВЫЙ', os.path.join(OUT, STEM + '.json'))):
    j = json.load(io.open(path, encoding='utf-8'))
    items = (j.get(KEY) or {}).get('items') or []
    rows = walk(items)
    depth1 = sum(1 for d, _, _ in rows if d == 0)
    depth2 = sum(1 for d, _, _ in rows if d > 0)
    codes = [c for _, c, _ in rows]
    print('%s: строк верхнего уровня %d, вложенных %d, всего %d'
          % (tag, depth1, depth2, len(rows)))
    print('   заполненных значений всего: %d' % filled(items))
    print('   есть ли 4111..4329 (глубокий разбор): %s'
          % sorted(set(c for c in codes if len(c) == 4 and c[1:3] in
                       ('11', '12', '13', '14', '19', '21', '22', '23', '24', '29', '31', '32', '39')))[:8])
    print('   первые 8 кодов: %s' % codes[:8])
    print()
