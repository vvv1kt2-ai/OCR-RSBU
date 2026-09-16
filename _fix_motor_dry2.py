# -*- coding: utf-8 -*-
r"""Полная арифметическая проверка «Моторные технологии_6мес_2025» по всем колонкам.

Прошлый прогон дал сильную улику (1600-1100 совпало с values_ocr1 для 1200 во всех трёх
колонках), но сумму по слагаемым не посчитал — в карту значений не попали компоненты, и
проверка «1100 = 1110+1150+...» молча выродилась в «проверить нельзя». Это тот же класс
ошибки, что и раньше: инструмент соврал не результатом, а пропуском.

Здесь печатаем ПОЛНЫЕ массивы трёх колонок и все тождества формы 0710001.
"""
import io, json, os

EX = r'D:\models\extracted'
STEM = 'Моторные технологии_6мес_2025'
j = json.load(io.open(os.path.join(EX, STEM + '.json'), encoding='utf-8'))
bal = j.get('balance') or {}
items = bal.get('items') or []
cols = bal.get('columns') or []


def num(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    x = str(x).strip().replace(' ', '').replace('\u00a0', '')
    if x in ('', '-'):
        return None
    neg = x.startswith('(') and x.endswith(')')
    x = x.strip('()').replace(',', '.')
    try:
        return (-1 if neg else 1) * float(x)
    except ValueError:
        return None


def f(x):
    return '—' if x is None else ('%g' % x)


ROW = {}
for it in items:
    ROW[str(it.get('code') or '')] = it

SEC1 = ['1110', '1150', '1160', '1170', '1180', '1190']
SEC2 = ['1210', '1215', '1220', '1230', '1240', '1250', '1260']
SEC3 = ['1310', '1320', '1340', '1350', '1360', '1370']
SEC4 = ['1410', '1420', '1430', '1450']
SEC5 = ['1510', '1520', '1530', '1540', '1550']

print('=== ПОЛНЫЕ МАССИВЫ (действующие values | values_ocr1)')
print('%-6s %-30s %-34s %s' % ('код', 'имя', 'values', 'values_ocr1'))
for c, it in ROW.items():
    v = (it.get('values') or [])
    o = (it.get('values_ocr1') or [])
    if not o and not any(x not in ('', None) for x in v):
        continue
    print('%-6s %-30s %-34s %s' % (c, (it.get('name') or '')[:30],
                                   ' | '.join(f(num(x)) for x in v),
                                   ' | '.join(f(num(x)) for x in o) if o else ''))

print()
print('=== ТОЖДЕСТВА ФОРМЫ по колонкам (действующее состояние)')
for i, cn in enumerate(cols):
    def g(c, which='now'):
        it = ROW.get(c)
        if it is None:
            return None
        arr = (it.get('values') or []) if which == 'now' else (it.get('values_ocr1') or [])
        return num(arr[i]) if i < len(arr) else None

    print('колонка %d (%s):' % (i, cn))
    for tot, parts, label in (('1100', SEC1, 'разд. I'), ('1200', SEC2, 'разд. II'),
                              ('1300', SEC3, 'разд. III'), ('1400', SEC4, 'разд. IV'),
                              ('1500', SEC5, 'разд. V')):
        t = g(tot)
        have = [(p, g(p)) for p in parts if g(p) is not None]
        if t is None:
            print('   %-9s %s = %-10s  (пусто)' % (label, tot, '—'))
            continue
        if not have:
            print('   %-9s %s = %-10s  слагаемых нет' % (label, tot, f(t)))
            continue
        s = sum(x for _, x in have)
        flag = 'OK' if abs(t - s) < 0.5 else 'РАСХОЖДЕНИЕ %+g' % (t - s)
        print('   %-9s %s = %-10s сумма(%s) = %-10s %s'
              % (label, tot, f(t), '+'.join(p for p, _ in have), f(s), flag))
    b16, b17 = g('1600'), g('1700')
    s3 = sum(x for x in [g('1300'), g('1400'), g('1500')] if x is not None)
    print('   1600=%s  1700=%s  1300+1400+1500=%s  %s'
          % (f(b16), f(b17), f(s3), 'OK' if b16 is not None and abs(b16 - s3) < 0.5 else 'проверить нельзя/расхождение'))

print()
print('=== ЕСЛИ ПРИМЕНИТЬ ПРАВКУ (values_ocr1 для стёртых ячеек колонки 0)')
for i in (0,):
    def h(c):
        it = ROW.get(c)
        if it is None:
            return None
        v = (it.get('values') or [])
        o = (it.get('values_ocr1') or [])
        a = v[i] if i < len(v) else None
        b = o[i] if i < len(o) else None
        return num(b) if (a in ('', None) and b not in ('', None)) else num(a)
    for tot, parts, label in (('1200', SEC2, 'разд. II'),):
        t = h(tot)
        have = [(p, h(p)) for p in parts]
        s = sum(x for _, x in have if x is not None)
        print('   %s: %s = %s  сумма(%s) = %s  -> %s'
              % (label, tot, f(t), '+'.join('%s=%s' % (p, f(x)) for p, x in have), f(s),
                 'OK, расхождение 0' if t is not None and abs(t - s) < 0.5 else 'расхождение %+g' % ((t or 0) - s)))
    b16, b11 = h('1600'), h('1100')
    print('   1600 - 1100 = %s  и  1200 = %s  -> %s'
          % (f(b16 - b11 if b16 is not None and b11 is not None else None), f(h('1200')),
             'СОВПАЛО, баланс сходится' if b16 is not None and b11 is not None and h('1200') is not None
             and abs((b16 - b11) - h('1200')) < 0.5 else 'проверить'))
