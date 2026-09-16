# -*- coding: utf-8 -*-
r"""Проверка правки дублей кодов — офлайн, на УЖЕ ОПЛАЧЕННОМ кэше ответов модели.

Что проверяется:
 1) сама функция на синтетических случаях: повтор строки (сливать), пустой второй дубль
    (складывать безвредно), две разные строки с одним кодом (складывать);
 2) на кэше структурирования extracted/pages/_llm_*_tstruct_*_pv.json — где модель вернула
    один код дважды, что стало со строкой и с тождеством раздела ДО правки (как было:
    второй код становился ребёнком, свод видел первый) и ПОСЛЕ (со сложением).

Сравнение идёт ПРОИЗВОДСТВЕННОЙ функцией P.run_checks, а не своей арифметикой.
В сеть не ходит, денег не тратит, ничего не пишет.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

PAGES = r'D:\models\extracted\pages'
fail = []


def chk(cond, label, extra=''):
    if not cond:
        fail.append(label)
    print(f'  [{"ok " if cond else "ПРОВАЛ"}] {label}{(" — " + extra) if extra else ""}')


def mk(code, name, vals):
    return {'code': code, 'name': name, 'values': list(vals),
            'raw_values': [('' if v is None else str(v)) for v in vals]}


# ---------------------------------------------------------------- 1) синтетика
print('1) синтетические случаи')
# 1а. две РАЗНЫЕ строки с одним кодом (Моторные: денежные средства + депозитные счета)
items = [mk('1250', 'Денежные средства и денежные эквиваленты', [4070, 4070, 4070]),
         mk('1250', 'Депозитные счета', [14500, 87800, None])]
w = []
out = P.merge_duplicate_codes(items, warnings=w)
chk(len(out) == 1, 'два item с кодом 1250 слились в один', f'строк {len(out)}')
chk(out[0]['values'] == [18570, 91870, 4070], 'значения сложены по колонкам',
    str(out[0]['values']))
chk(len(w) == 1 and 'сложены' in w[0], 'предупреждение названо и говорит «сложены»',
    (w or ['<нет>'])[0][:70])

# 1б. ПОВТОР: та же строка пришла дважды (документированный дефект Polza) — удваивать нельзя
items = [mk('1520', 'Краткосрочные заёмные средства', [100, 200, 300]),
         mk('1520', 'Краткосрочные заёмные средства', [100, 200, 300])]
w = []
out = P.merge_duplicate_codes(items, warnings=w)
chk(out[0]['values'] == [100, 200, 300], 'повтор НЕ удвоен', str(out[0]['values']))
chk('слиты' in (w or [''])[0], 'предупреждение говорит «слиты, не сложены»',
    (w or ['<нет>'])[0][:70])

# 1в. ПОВТОР с частично пустой второй копией — берём заполненное
items = [mk('1220', 'НДС', [None, 500, 600]), mk('1220', 'НДС', [None, None, 600])]
out = P.merge_duplicate_codes(items)
chk(out[0]['values'] == [None, 500, 600], 'частично пустой повтор слит по колонкам',
    str(out[0]['values']))

# 1г. ПУСТОЙ второй дубль (Байсэл/Йуми: 1220 = «-») — складывать безвредно
items = [mk('1220', 'НДС, начисленный по отгрузке', [700, 800, 900]),
         mk('1220', 'НДС, начисленный по отгрузке', [None, None, None])]
out = P.merge_duplicate_codes(items)
chk(out[0]['values'] == [700, 800, 900], 'пустой второй дубль значение не меняет',
    str(out[0]['values']))

# 1д. вложенные строки слитой строки не пропадают
items = [mk('1250', 'A', [1, None, None]), mk('1250', 'B', [2, None, None])]
items[1]['children'] = [mk(None, 'деталь', [5, None, None])]
out = P.merge_duplicate_codes(items)
chk(len(out[0].get('children') or []) == 1, 'вложенные строки слитой строки сохранены')

# 1е. не-верхнеуровневые коды не трогаем (это законная детализация)
items = [mk('4111', 'A', [1, None, None]), mk('4111', 'B', [2, None, None])]
out = P.merge_duplicate_codes(items)
chk(len(out) == 1, 'дубль 4111 (входит в KNOWN_TOP) тоже слит', f'строк {len(out)}')

# ---------------------------------------------------------------- 2) реальные документы
print()
print('2) реальные ответы модели из кэша структурирования (plusvibe)')


def old_normalize(llm, form_key=None):
    """Как было ДО правки: дубль верхнеуровневого кода понижался в ребёнка."""
    raw = llm.get('items', [])
    if form_key == 'balance':
        P._assign_bal_codes(raw)
    items, seen = [], set()
    for it in raw:
        code = it.get('code')
        rec = {'code': code, 'name': it.get('name'), 'values': it.get('values'),
               'raw_values': it.get('raw_values', it.get('values')),
               'children': it.get('children', []) or []}
        if code and code in P.KNOWN_TOP and code not in seen:
            seen.add(code)
            items.append(rec)
        elif items:
            items[-1].setdefault('children', []).append(rec)
        else:
            items.append(rec)
    return items


def sections_of(form_key):
    if form_key == 'balance':
        return {'1200': ['1210', '1215', '1220', '1230', '1240', '1250', '1260'],
                '1500': ['1510', '1520', '1530', '1540', '1550'],
                '1100': ['1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180', '1190']}
    return {}


def vals_of(items, code):
    """значения кода на верхнем уровне (последнее вхождение — как svod.get_val)"""
    hit = [it for it in items if it.get('code') == code]
    return hit[-1].get('values') if hit else None


docs = {}
for f in glob.glob(os.path.join(PAGES, '_llm_*_tstruct_*_pv.json')):
    b = os.path.basename(f)
    m = re.match(r'^_llm_(?P<doc>.+)_tstruct_(?P<form>[a-z_]+)_p[\d_]+_pv\.json$', b)
    if m:
        docs.setdefault((m.group('doc'), m.group('form')), f)

print(f'  кэшей структурирования plusvibe: {len(docs)}')
found = 0
for (doc, form), f in sorted(docs.items()):
    try:
        llm = json.load(open(f, encoding='utf-8'))
    except Exception as e:
        print(f'  {doc[:30]} {form}: не прочитан ({e})')
        continue
    raw = llm.get('items') or []
    occ = {}
    for it in raw:
        c = it.get('code')
        if c and c in P.KNOWN_TOP:
            occ.setdefault(c, []).append(it)
    dups = {c: v for c, v in occ.items() if len(v) >= 2}
    if not dups:
        continue
    found += 1
    print(f'  {doc[:34]} / {form}: дубли кодов {sorted(dups)}')
    old_items = old_normalize(llm, form)
    w = []
    new_items = P._normalize_llm(llm, form, warnings=w)
    for c in sorted(dups):
        o, n = vals_of(old_items, c), vals_of(new_items, c)
        names = ' + '.join((x.get('name') or '')[:26] for x in dups[c])
        print(f'     {c}: до {o} -> после {n}   ({names})')
    # тождество раздела: производственная функция run_checks
    for label, items in (('до', old_items), ('после', new_items)):
        chks = P.run_checks(form, items)
        bad = [c['rule'][:14] for c in chks if not c['ok']]
        print(f'     проверки {label:5}: провалов {len(bad)} {bad}')
    for line in w:
        print(f'     предупреждение: {line[:110]}')
    # отдельно: сошлось ли тождество раздела там, где дубль входит в раздел
    secs = sections_of(form)
    for tot, parts in secs.items():
        ncols = max((len(it.get('values') or []) for it in new_items), default=0)
        for col in range(ncols):
            def g(items, code):
                v = vals_of(items, code)
                return v[col] if v and col < len(v) else None
            tv = g(new_items, tot)
            if tv is None:
                continue
            s_old = sum(x for x in (g(old_items, p) for p in parts) if x is not None)
            s_new = sum(x for x in (g(new_items, p) for p in parts) if x is not None)
            if abs(tv - s_old) < 1 and abs(tv - s_new) >= 1:
                fail.append(f'{doc} {tot} кол.{col}: правка СЛОМАЛА тождество')
            if abs(tv - s_new) < 1 and abs(tv - s_old) >= 1:
                print(f'     раздел {tot} кол.{col}: до {s_old} (не сходилось), '
                      f'после {s_new} = {tv} — СОШЛОСЬ')

print()
print(f'документов с дублями в кэше: {found}')

# ---------------------------------------------------------------- 3) пересечение со сводом
# Свод (svod_build) не просто читает коды: он ещё и прибавляет аренду к 1450/1550 правилом
# rent_extract, которое ходит ПО ВЛОЖЕННЫМ строкам. Пока дубль 1520 был ребёнком, свод его
# в 1520 не видел, но в 1550 прибавлял. После слияния строка попадает И в 1520 — надо
# убедиться, что она не посчитана дважды в одной и той же ячейке.
print()
print('3) пересечение с правилом аренды свода (rent_extract)')
import svod  # noqa: E402

for (doc, form), f in sorted(docs.items()):
    if form != 'balance':
        continue
    try:
        llm = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    raw = llm.get('items') or []
    occ = {}
    for it in raw:
        c = it.get('code')
        if c and c in P.KNOWN_TOP:
            occ.setdefault(c, []).append(it)
    if not any(len(v) >= 2 for v in occ.values()):
        continue
    res = {}
    for label, items in (('до', old_normalize(llm, form)),
                         ('после', P._normalize_llm(llm, form))):
        bal = {'items': items, 'columns': llm.get('columns') or []}
        svod.mark_chains(bal)
        n = max((len(it.get('values') or []) for it in items), default=0)
        row = []
        for col in range(n):
            lv, shv, notes, susp = svod.rent_extract(bal, col)
            g = lambda c: (vals_of(items, c) or [None] * (col + 1))[col]  # noqa: E731
            row.append(f'1450={g("1450")}+{lv} 1550={g("1550")}+{shv} 1520={g("1520")}')
        res[label] = row
    print(f'  {doc[:34]} / {form}')
    for col, (a, b) in enumerate(zip(res['до'], res['после'])):
        print(f'     кол.{col} до   : {a}')
        print(f'     кол.{col} после: {b}')
        if a != b:
            print('     ^^ изменилось')

print()
print('ИТОГ: ' + ('всё зелено' if not fail else f'ПРОВАЛОВ {len(fail)}: {fail[:5]}'))
