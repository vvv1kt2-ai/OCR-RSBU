# -*- coding: utf-8 -*-
r"""Проверка правки 2 без оплаты: категории, разбор ответа, ключ кэша."""
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P

print('версия подсказки детекции: %r' % P.DETECT_PROMPT_VERSION)
print('категории страниц: %s' % (P.PAGE_LABELS,))
print('метки форм: %s' % (P.FORM_LABELS,))
print()

t = '{"1":"balance","2":"notes","3":"audit","4":"other","5":"income_statement"}'
print('salvage понимает notes/audit:')
print('   %s' % P.salvage_pages_map(t, 10))
print()

print('подсказка требует новые категории:')
for w in ('notes', 'audit', 'ПОЯСНЕНИЯ', 'АУДИТОРСКОЕ', 'ДО баланса'):
    print('   %-14s %s' % (w, 'есть' if w in P.DETECT_PROMPT else 'НЕТ'))
print()

print('ключ кэша детекции:')
print('   старый: <документ>_detect            <- ответы старой подсказки')
print('   новый:  <документ>_detect_%s        <- ответы новой подсказки' % P.DETECT_PROMPT_VERSION)
print()
print('без смены версии кэш вернул бы старые метки и правка не дала бы эффекта.')
