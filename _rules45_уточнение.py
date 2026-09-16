# -*- coding: utf-8 -*-
r"""Уточнение к _rules45_замер.py — два вопроса.

1) Почему «Простая еда_6мес_2025» не сходится по разделу IV: каких кодов не хватает
   в нашем списке (то есть правило даст ЛОЖНЫЙ провал, а ложный провал покупает эскалацию).

2) Сколько документов останется падать ПОСЛЕ правки дублей. Первый замер применял слияние
   к СОХРАНЁННЫМ артефактам, а там дубль уже лежит ВЛОЖЕННОЙ строкой — слияние верхнего
   уровня его не видит и мерило получилось неверным. Здесь состояние «новый прогон»
   восстанавливается честно: строки-дети, чей код дублирует верхнеуровневый, поднимаются
   наверх — ровно так их увидит новый разбор — и только потом сливаются.
"""
import glob
import io
import json
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

EX = r'D:\models\extracted'
TOL = 2
RULES = {
    'IV 1400': ('1400', ('1410', '1420', '1430', '1440', '1450')),
    'V  1500': ('1500', ('1510', '1520', '1530', '1540', '1550')),
}


def vals(items, code):
    hit = [it for it in items if it.get('code') == code]
    return (hit[-1].get('values') or []) if hit else None


def bad_cols(items, total, parts):
    tv = vals(items, total)
    if not tv:
        return None
    out = []
    for c in range(len(tv)):
        if tv[c] is None:
            continue
        have = [(p, a[c]) for p in parts
                if (a := vals(items, p)) and c < len(a) and a[c] is not None]
        if not have:
            continue
        s = sum(v for _, v in have)
        if abs(tv[c] - s) > TOL:
            out.append((c, tv[c], s, tv[c] - s, have))
    return out


def new_run_items(stored):
    """восстановить, что увидит новый разбор: дубли-дети поднимаются наверх, потом слияние"""
    top = {it.get('code') for it in stored if it.get('code')}
    flat = list(stored)
    for it in stored:
        for ch in it.get('children') or []:
            c = ch.get('code')
            if c and c in P.KNOWN_TOP and c in top:
                flat.append({'code': c, 'name': ch.get('name'),
                             'values': ch.get('values') or [],
                             'raw_values': ch.get('raw_values') or []})
    return P.merge_duplicate_codes(flat)


docs = []
for path in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(path)
    if b.startswith('_'):
        continue
    try:
        j = json.load(io.open(path, encoding='utf-8'))
    except Exception:
        continue
    items = (j.get('balance') or {}).get('items') or []
    if items:
        docs.append((b[:-5], items))

print('1) «Простая еда_6мес_2025»: какие коды вообще есть в разделе IV')
for name, items in docs:
    if not name.startswith('Простая еда_6мес_2025'):
        continue
    codes = [it.get('code') for it in items if it.get('code')]
    print(f'   все коды верхнего уровня: {codes}')
    print(f'   дети: {[(ch.get("code"), ch.get("name"), ch.get("values")) for it in items for ch in (it.get("children") or [])][:6]}')
    for c in ('1400', '1410', '1420', '1430', '1440', '1450', '1460', '1435', '1420'):
        v = vals(items, c)
        if v:
            print(f'   {c} = {v}')
print()

print('2) провалы: как есть (старый код) -> новый прогон (с подъёмом и слиянием дублей)')
for label, (total, parts) in RULES.items():
    n0 = n1 = 0
    detail = []
    for name, items in docs:
        b0 = bad_cols(items, total, parts) or []
        b1 = bad_cols(new_run_items(items), total, parts) or []
        n0 += bool(b0)
        n1 += bool(b1)
        if b0 or b1:
            detail.append((name, b0, b1))
    print(f'  {label}: {n0} -> {n1}')
    for name, b0, b1 in detail:
        def f(b):
            if not b:
                return 'сошлось'
            c, t, s, d, have = b[0]
            return f'кол.{c} {d:+d} ({[f"{p}={v}" for p, v in have]})'
        print(f'    {name[:34]:34} до {f(b0)}')
        print(f'    {"":34} после {f(b1)}')
    print()
