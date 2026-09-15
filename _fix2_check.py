# -*- coding: utf-8 -*-
r"""Проверка правки 2 после отката текста подсказки (без оплаты).

Текст подсказки откачен к исходному (правка увеличивала чтение на 32% без доказанной
пользы), но всё остальное из правки 2 осталось: категории notes/audit понимаются кодом,
задел non_form_pages пишется в артефакт, титульный лист читается как title_p1, а ключ
кэша следует за текстом подсказки.
"""
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P

print('текст подсказки откачен: %s'
      % ('ДА' if 'notes' not in P.DETECT_PROMPT else 'НЕТ'))
print('категории страниц: %s' % (P.PAGE_LABELS,))
print('метки форм: %s' % (P.FORM_LABELS,))
print()

t = '{"1":"balance","2":"notes","3":"audit","4":"other","5":"income_statement"}'
print('salvage понимает notes/audit (задел на будущее):')
print('   %s' % P.salvage_pages_map(t, 10))
print()

print('ключ кэша следует за текстом подсказки:')
print('   исходный текст:   %r' % P.detect_cache_stem('ТГК-14_6мес_2025.pdf'))
print('   изменённый текст: %r'
      % P.detect_cache_stem('ТГК-14_6мес_2025.pdf', P.DETECT_PROMPT + ' x'))
print()
print('ручной константы версии больше нет — её нельзя забыть поднять.')
