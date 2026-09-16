# -*- coding: utf-8 -*-
r"""Что дадут правила на СОСТАВ разделов IV и V — замер без вызовов моделей.

Правила-кандидаты:
    раздел IV (долгосрочные обязательства): 1400 = 1410+1420+1430+1440+1450
    раздел V  (краткосрочные обязательства): 1500 = 1510+1520+1530+1540+1550

Считается в двух состояниях: КАК ЕСТЬ (артефакты сделаны прежним кодом) и ПОСЛЕ СЛИЯНИЯ
ДУБЛЕЙ (новый код). Печатает только сводку + провалы, чтобы ответить на вопрос «сколько
документов это затронет и сколько будет стоить».

Отдельно печатается, какие коды попадут эскалатору: он берёт их РЕГУЛЯРКОЙ ИЗ ТЕКСТА
ПРАВИЛА (pipeline.escalate_failed_form -> codes_from_checks), а не из данных.
"""
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

EX = r'D:\models\extracted'
TOL = 2

RULES = {
    'IV 1400=1410+1420+1430+1440+1450': ('1400', ('1410', '1420', '1430', '1440', '1450')),
    'V  1500=1510+1520+1530+1540+1550': ('1500', ('1510', '1520', '1530', '1540', '1550')),
}


def vals(items, code):
    hit = [it for it in items if it.get('code') == code]
    return (hit[-1].get('values') or []) if hit else None


def check(items, total, parts):
    """(провалов, непроверяемых) по колонкам; непроверяемое печатается отдельно"""
    tv = vals(items, total)
    if not tv:
        return None
    bad, vac = [], []
    for c in range(len(tv)):
        t = tv[c]
        if t is None:
            continue
        add = [vals(items, p) for p in parts]
        have = [(p, a[c]) for p, a in zip(parts, add) if a and c < len(a) and a[c] is not None]
        if not have:
            vac.append(c)
            continue
        s = sum(v for _, v in have)
        if abs(t - s) > TOL:
            bad.append((c, t, s, t - s, have))
    return bad, vac


present = {}
rows = []
for path in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(path)
    if b.startswith('_'):
        continue
    try:
        j = json.load(io.open(path, encoding='utf-8'))
    except Exception:
        continue
    bal = j.get('balance') or {}
    items = bal.get('items') or []
    if not items:
        continue
    merged = P.merge_duplicate_codes([dict(it) for it in items])
    for _, (total, parts) in RULES.items():
        for p in (total,) + parts:
            if vals(items, p):
                present[p] = present.get(p, 0) + 1
    rows.append((b[:-5], items, merged))

print('коды разделов IV и V: сколько балансов из %d их вообще содержат' % len(rows))
for c in ('1400', '1410', '1420', '1430', '1440', '1450',
          '1500', '1510', '1520', '1530', '1540', '1550'):
    print(f'   {c}: {present.get(c, 0)}')
print()

print('провалы правил (допуск %d): как есть -> после слияния дублей' % TOL)
for label, (total, parts) in RULES.items():
    now = [d for d, it, _ in rows if check(it, total, parts) and check(it, total, parts)[0]]
    after = [d for d, _, mg in rows if check(mg, total, parts) and check(mg, total, parts)[0]]
    print(f'  {label}: {len(now)} -> {len(after)}')
    for d, it, mg in rows:
        r0, r1 = check(it, total, parts), check(mg, total, parts)
        b0 = r0[0] if r0 else []
        b1 = r1[0] if r1 else []
        if b0 or b1:
            def fmt(bad):
                if not bad:
                    return 'сошлось'
                c, t, s, diff, have = bad[0]
                return f'кол.{c}: итог {t}, сумма {s} ({diff:+d}) из {[f"{p}={v}" for p, v in have]}'
            print(f'    {d[:34]:34} до: {fmt(b0)}')
            print(f'    {"":34} после: {fmt(b1)}')
    print()

print('коды, которые эскалатор пойдёт перечитывать (берутся из ТЕКСТА правила):')
for label, (total, parts) in RULES.items():
    toks = re.findall(r'(?<![\d-])\d{4}(?![\d-])', label)
    print(f'  {label} -> {sorted(set(toks))} ({len(set(toks))} кодов)')
