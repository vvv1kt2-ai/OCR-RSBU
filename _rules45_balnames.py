# -*- coding: utf-8 -*-
r"""Проверка правки BAL_NAMES на УЖЕ ОПЛАЧЕННОМ кэше ответа модели.

«Простая еда_6мес_2025»: страница пассива расшифрована БЕЗ колонки кодов, поэтому коды
расставляются по именам (_assign_bal_codes). В таблице BAL_NAMES нет названий
«Прочие долгосрочные обязательства» (1450) и «Доходы будущих периодов» (1530) —
и ровно эти две строки пропали: 199788 и 2335.

Считаем тождества разделов IV и V производственной функцией run_checks в двух состояниях:
с текущей таблицей имён и с дополненной. Вызовов моделей нет.
"""
import io
import json
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

CACHE = r'D:\models\extracted\pages\_llm_Простая еда_6мес_2025_struct_balance_pv.json'

ADD = {
    'прочиедолгосрочныеобязательства': ['1450'],
    'доходыбудущихпериодов': ['1530'],
    'прочиекраткосрочныеобязательства': ['1550'],
}


def rows(items):
    out = []
    for it in items:
        out.append((it.get('code'), it.get('name'), it.get('values')))
        for ch in it.get('children') or []:
            out.append((ch.get('code'), ch.get('name'), ch.get('values')))
    return out


def section_state(items):
    """раздел IV и V: итог и сумма слагаемых по колонке 0"""
    def v(code):
        hit = [it for it in items if it.get('code') == code]
        return (hit[-1].get('values') or [None])[0] if hit else None
    res = {}
    for total, parts in (('1400', ('1410', '1420', '1430', '1440', '1450')),
                         ('1500', ('1510', '1520', '1530', '1540', '1550'))):
        have = [(p, v(p)) for p in parts if v(p) is not None]
        res[total] = (v(total), sum(x for _, x in have), have)
    return res


llm = json.load(io.open(CACHE, encoding='utf-8'))
print(f'в сыром ответе модели строк: {len(llm.get("items") or [])}')

for label, extra in (('как есть', {}), ('с дополненной таблицей имён', ADD)):
    saved = dict(P.BAL_NAMES)
    P.BAL_NAMES.update(extra)
    items = P._normalize_llm(json.loads(json.dumps(llm)), 'balance')
    P.BAL_NAMES.clear()
    P.BAL_NAMES.update(saved)
    print(f'\n=== {label}')
    st = section_state(items)
    for total in ('1400', '1500'):
        t, s, have = st[total]
        mark = 'СОШЛОСЬ' if (t is not None and abs(t - s) <= 2) else 'НЕ сходится'
        print(f'  {total}: итог {t}, сумма {s} ({mark})  слагаемые: '
              f'{[(p, x) for p, x in have]}')
    chks = P.run_checks('balance', items)
    print(f'  проверки run_checks: провалов {sum(1 for c in chks if not c["ok"])} из {len(chks)}')
    if extra:
        print('  строки, которые появились благодаря именам:')
        for c, n, vals in rows(items):
            if c in ('1450', '1530', '1550') and vals and any(x is not None for x in vals):
                print(f'    {c} {(n or "")[:42]} {vals}')
