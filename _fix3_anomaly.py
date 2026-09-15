# -*- coding: utf-8 -*-
r"""Почему сохранённые проверки ОДДС у ИПС_6мес_2026 расходятся с пересчётом.

Правка 3 касалась только правил баланса, поэтому изменение у cash_flow —
подозрительное. Либо в сохранённых `checks` устаревшие данные, либо я где-то
ошибаюсь. Проверяю по значениям.
"""
import io, os, json, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
STEM = 'ИПС_6мес_2026'

doc = json.load(io.open(os.path.join(EX, STEM + '.json'), encoding='utf-8'))
print('текстовый слой:', (doc.get('source') or {}).get('text_layer'))
print('предупреждения:')
for w in (doc.get('warnings') or []):
    print('   %s' % w[:150])
print()

items = (doc.get('cash_flow') or {}).get('items') or []
print('сохранённые проверки cash_flow:')
for c in (doc.get('checks') or []):
    if c['form'] == 'cash_flow':
        print('   %-40s ok=%-5s per_column=%s' % (c['rule'][:40], c.get('ok'), c.get('per_column')))
print('пересчитанные проверки cash_flow:')
for c in P.run_checks('cash_flow', items):
    print('   %-40s ok=%-5s per_column=%s' % (c['rule'][:40], c.get('ok'), c.get('per_column')))
print()

m = P.val_map(items)
print('значения нужных кодов (по колонкам):')
for code in ('4100', '4110', '4120', '4200', '4210', '4220', '4300', '4310', '4320',
             '4400', '4450', '4490', '4500'):
    print('   %s: %s' % (code, m.get(code)))
print()

print('строк в cash_flow: %d' % len(items))
print('коды строк: %s' % [it.get('code') for it in items])
print()
print('пометки исправлений/подтверждений:')
for it in items:
    if it.get('corrected_by') or it.get('confirmed_by') or it.get('values_ocr1'):
        print('   %s: values=%s ocr1=%s corrected=%s confirmed=%s'
              % (it.get('code'), it.get('values'), it.get('values_ocr1'),
                 it.get('corrected_by'), it.get('confirmed_by')))
