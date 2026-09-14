# -*- coding: utf-8 -*-
r"""Во что обошлись собственные вызовы агента и есть ли цена у рассуждений.

Модель агента и модель детекции — одна и та же (совпадает длина имени и sha1),
поэтому цену берём из профиля по отпечатку, а не по имени: вывод подменяет
идентификаторы моделей пустой строкой, поэтому сравнивать надо численно.
"""
import io, json, hashlib, sys

sys.path.insert(0, r'D:\models')
import providers as PR

# отпечатки, установленные ранее в разборе
DETECT_LEN, DETECT_SHA = 19, '9ab9da1f08'

prof = PR.active('plusvibe')
print('профиль: %s' % prof.name)
print()

found = []
for name, spec in (getattr(prof, 'variants', {}) or {}).items():
    h = hashlib.sha1(name.encode('utf-8')).hexdigest()[:10]
    found.append((name, h, spec))
for name, h, spec in found:
    mark = ''
    if len(name) == DETECT_LEN and h == DETECT_SHA:
        mark = '  <-- модель детекции и агента'
    print('  len=%-3d sha1=%s  %s%s' % (len(name), h, spec, mark))
print()

# цена нужной модели
price = None
for name, h, spec in found:
    if len(name) == DETECT_LEN and h == DETECT_SHA:
        price = spec
if price is None:
    print('модель по отпечатку не найдена в вариантах профиля')
    print('варианты профиля содержат %d записей' % len(found))
else:
    print('цена модели (по отпечатку): %s' % price)
print()

# расход агента из разбора лога
u = json.load(io.open(r'D:\models\_session_usage.json', encoding='utf-8'))
print('=== расход агента за сессию ===')
print('  шагов: %d' % u['rows'])
print('  вход: %.1f млн токенов (медиана на шаг %d)' % (u['prompt_sum'] / 1e6,
                                                        u['prompt_median']))
print('  выход: %.1f тыс. токенов' % (u['out_sum'] / 1e3))
print('  время модели: %.2f ч' % u['model_hours'])
print()

# прикидка цены при разных тарифах
print('=== сколько это стоило бы при разных тарифах ===')
print('(точный тариф зависит от того, как поставщик считает кэш)')
for rub_in in (0.3, 1.0, 3.78):
    for rub_out in (18.86,):
        cost = u['prompt_sum'] / 1e6 * rub_in + u['out_sum'] / 1e6 * rub_out
        print('  вход %.2f ₽/млн, выход %.2f ₽/млн -> %.1f ₽' % (rub_in, rub_out, cost))
print()
print('  для сравнения: вся работа скриптов за сессию (детекция, эскалация, замеры)')
print('  обошлась примерно в 30-35 ₽ по счетам провайдеров.')
