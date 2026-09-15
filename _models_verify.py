# -*- coding: utf-8 -*-
r"""Проверка отчёта о моделях: какие модели реально стоят в ролях и сколько стоят.

В этой среде идентификаторы моделей в выводе подменяются пустой строкой, поэтому
печатаю длину, sha1 и ord-коды — по ним строки различимы, а глазами нет.
"""
import sys, hashlib, json

sys.path.insert(0, r'D:\models')
import providers as PR

for name in ('polza', 'plusvibe'):
    try:
        p = PR.active(name)
    except Exception as e:
        print('%s: ОШИБКА %s' % (name, e))
        continue
    print('=== %s' % name)
    for role in ('detect', 'main', 'esc'):
        m = p.roles.get(role)
        if m is None:
            print('  %-7s (нет)' % role)
            continue
        h = hashlib.sha1(m.encode('utf-8')).hexdigest()[:10]
        ords = ','.join(str(ord(c)) for c in m[:4])
        try:
            pin, pout = p.price_of(m)
            price = '%.2f / %.2f ₽ за 1М' % (pin, pout)
        except Exception as e:
            price = 'цена: ошибка %s' % e
        print('  %-7s len=%-3d sha1=%s ords=%s  %s' % (role, len(m), h, ords, price))
    print()

print('=== совпадают ли роли между провайдерами ===')
try:
    a, b = PR.active('polza'), PR.active('plusvibe')
    for role in ('detect', 'main', 'esc'):
        same = a.roles.get(role) == b.roles.get(role)
        print('  %-7s %s' % (role, 'одинаковые' if same else 'РАЗНЫЕ'))
except Exception as e:
    print('  ошибка', e)

print()
print('=== проверка: сходится ли цена эскалации с измеренной (0.708 ₽/стр.) ===')
try:
    pv = PR.active('plusvibe')
    ein, eout = pv.price_of(pv.roles['esc'])
    page = 4781 / 1e6 * ein + 1932 / 1e6 * eout
    print('  PlusVibe эскалация: %.3f ₽/стр. (измерено 0.708)' % page)
    pz = PR.active('polza')
    zin, zout = pz.price_of(pz.roles['esc'])
    zpage = 4781 / 1e6 * zin + 1932 / 1e6 * zout
    print('  Polza   эскалация: %.3f ₽/стр. (измерено 2.12)' % zpage)
except Exception as e:
    print('  ошибка', e)
