# -*- coding: utf-8 -*-
r"""Потеряны данные или только КОД строки? Ищем сами числа в новом артефакте.

Сравнение по кодам дало 87 «потерь». Но адресация по коду — это способ свода, а не истина
о данных: если строка осталась, но потеряла код (стала детализацией «в том числе» без кода),
то число на месте, а свод его просто не адресует. Это разные вещи, и путать их нельзя.

Для каждого подозрительного значения проверяем, встречается ли это число ГДЕ-НИБУДЬ в новой
форме (в любой строке, на любом уровне). Три возможных исхода:
  НА МЕСТЕ   — число есть в новой форме, потерян только код строки;
  ПОТЕРЯНО   — числа нет нигде: данные исчезли;
  ИЗМЕНИЛОСЬ — на месте кода стоит другое число (тогда это не потеря, а расхождение чтения).
"""
import io, json, os, re

OUT = r'D:\models\extracted'
BAK = os.path.join(OUT, '_backup_v2_before')
CASES = [('Артген (ИСКЧ)_6мес_2026', 'cash_flow', ['4111', '4121', '4123']),
         ('Байсэл_6мес_2026', 'cash_flow', ['4111', '4121']),
         ('Корпсан_6мес_2026', 'cash_flow', ['4111', '4213']),
         ('Славянск ЭКО_6мес_2025', 'balance', ['1220']),
         ('Моторные технологии_6мес_2025', 'balance', ['1200', '1220'])  # затёртый столбец
         ]
CODE = re.compile(r'^\d{4}$')


def load(p):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except Exception:
        return None


def walk(items, d=0):
    for it in items or []:
        yield d, str(it.get('code') or ''), it.get('name') or '', \
            [('' if v is None else str(v)) for v in (it.get('values') or [])]
        yield from walk(it.get('children'), d + 1)


def numeric(s):
    return re.sub(r'\D', '', s or '')


for stem, key, codes in CASES:
    o, n = load(os.path.join(BAK, stem + '.json')), load(os.path.join(OUT, stem + '.json'))
    oi = (o or {}).get(key) or {}
    ni = (n or {}).get(key) or {}
    o_rows, n_rows = list(walk(oi.get('items'))), list(walk(ni.get('items')))
    n_vals = {numeric(v) for _, _, _, vals in n_rows for v in vals if v}
    print('=' * 92)
    print('%s / %s' % (stem, key))
    for code in codes:
        src = [r for r in o_rows if r[1] == code]
        if not src:
            continue
        _, _, name, vals = src[-1]
        print('  код %s (%s)' % (code, name[:40]))
        for i, v in enumerate(vals):
            if v == '':
                continue
            nv = numeric(v)
            if nv in n_vals:
                # найдём, где именно
                where = [r for r in n_rows if any(numeric(x) == nv for x in r[3] if x)]
                w = where[0]
                print('     кол.%d %-14s -> НА МЕСТЕ, но в строке %s (код «%s», уровень %d)'
                      % (i, v, ('есть' if w[1] else 'БЕЗ КОДА'), w[1] or '—', w[0]))
            else:
                same_code = [r for r in n_rows if r[1] == code]
                if same_code:
                    got = same_code[-1][3][i] if i < len(same_code[-1][3]) else ''
                    print('     кол.%d %-14s -> ИЗМЕНИЛОСЬ на «%s»' % (i, v, got))
                else:
                    print('     кол.%d %-14s -> ПОТЕРЯНО (числа нет нигде)' % (i, v))
    print()
