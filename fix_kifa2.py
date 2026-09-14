# -*- coding: utf-8 -*-
"""Патч КИФА_6мес_2026: добавить хвост ОДДС (стр. 11) с подтверждёнными значениями."""
import json
import sys

EXTRACTED = 'D:/models/extracted'
sys.path.insert(0, 'D:/models/pylibs')
import svod

d = json.load(open(f'{EXTRACTED}/КИФА_6мес_2026.json', encoding='utf-8'))
cf = d['cash_flow']

# Хвост ОДДС, перечитан со стр. 11 PDF (captcha-free, модель gemini-3.8-flash)
new_items = [
    {"code": "4320", "name": "Платежи - всего", "values": [-725000, -245000], "children": [
        {"name": "собственникам (участникам) в связи с выкупом у них акций", "values": [None, None]},
        {"name": "на уплату дивидендов", "values": [None, None]},
        {"name": "в связи с погашением (выкупом) векселей", "values": [-725000, -245000]},
        {"name": "прочие платежи", "values": [None, None]},
    ]},
    {"code": "4300", "name": "Сальдо денежных потоков от финансовых операций", "values": [-100000, 5000]},
    {"code": "4400", "name": "Сальдо денежных потоков за период", "values": [-105214, -163840]},
    {"code": "4450", "name": "Остаток денежных средств на начало периода", "values": [140074, 232657]},
    {"code": "4500", "name": "Остаток денежных средств на конец периода", "values": [33356, 68817]},
    {"code": "4490", "name": "Величина влияния изменения курса иностранной валюты", "values": [-1504, None]},
]

# Добавляем к существующим строкам (после 4310)
cf['items'].extend(new_items)

fails = svod.check_cf(cf)
print('check_cf после патча:', fails or 'OK')

# Проверяем 4400 и 4500 вручную
for it in cf['items']:
    c = it.get('code')
    if c in ('4300','4400','4450','4490','4500'):
        print(f"  {c} {it['name'][:40]}: {it['values']}")

d['cash_flow'] = cf
d.setdefault('warnings', []).append(
    'Хвост ОДДС (4320, 4300, 4400, 4450, 4490, 4500) потерян при первичном структурировании; '
    'стр. 11 PDF перечитана верификацией (gemini-3.8-flash).')
with open(f'{EXTRACTED}/КИФА_6мес_2026.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print('\nФайл сохранён.')
