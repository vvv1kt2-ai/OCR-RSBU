# -*- coding: utf-8 -*-
r"""Tests for the PlusVibe quality check (ticket 01).

These pin the *acceptance criterion* of the quality check — a number present in the
reference and missing from the candidate must be caught — and the verdict rules that
turn per-page evidence into «годится / не годится». No network, no LLM calls.

Run:  python D:\models\tests\test_pv_quality.py
"""
import os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P          # importing it puts D:\models\pylibs on sys.path
import _pv_quality as Q

PASS, FAIL, LOG = [], [], []
_console = print


def print(*a, **k):
    LOG.append(' '.join(str(x) for x in a))
    _console(*a, **k)


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  %-4s %s%s' % ('ok' if cond else 'FAIL', name, ('  <- ' + str(detail)) if detail and not cond else ''))


def row(**kw):
    """one page's evidence with sane defaults"""
    r = {'stem': 'x', 'page': 1, 'len_polza': 1000, 'len_pv': 1000,
         'truncated': False, 'filtered': False}
    r.update(kw)
    return r


print('--- адрес модели и вариант ---')
check('вариант по умолчанию идёт без суффикса', Q.address('m/x', 'default') == 'm/x')
check('пустой вариант тоже без суффикса', Q.address('m/x', '') == 'm/x')
check('именованный вариант даёт суффикс', Q.address('m/x', 'network') == 'm/x:network')
check('разные варианты — разные адреса', Q.address('m/x', 'ag2') != Q.address('m/x', 'default'))

print('--- числа: извлечение ---')
check('пробел внутри числа не мешает', Q.norm_digits('1 234') == ['1234'])
check('неразрывный пробел не мешает', Q.norm_digits('1\u00a0234') == ['1234'])
check('минус и скобки не мешают', Q.norm_digits('(1 345)') == ['1345'])
check('две группы разрядов склеиваются', Q.norm_digits('1 234 567') == ['1234567'])
check('дробная часть идёт отдельным числом', Q.norm_digits('1 234,5') == ['1234', '5'])
check('числа через пробел не склеиваются в одно', Q.norm_digits('20 10 30') == ['10', '20', '30'])
check('числа сортируются', Q.norm_digits('300 20 1') == ['1', '20', '300'])
check('текст без чисел пуст', Q.norm_digits('нет тут чисел') == [])

print('--- критерий приёмки: потерянное число должно быть найдено ---')
same = 'Выручка 1 234\nСебестоимость 567'
d = Q.digit_diff(same, same)
check('совпадающие тексты не дают расхождений',
      d['absent'] == [] and d['undercount'] == [] and d['extra'] == [], d)
d = Q.digit_diff('Итого 1700', 'Итого 1710')
check('подмена цифры в сумме ловится', d['absent'] == ['1700'] and d['extra'] == ['1710'], d)
d = Q.digit_diff('А 100\nБ 200', 'А 100')
check('пропавшая строка ловится', d['absent'] == ['200'] and d['extra'] == [], d)
d = Q.digit_diff('А 100\nА 100', 'А 100')
check('пропажа кратности — это не «нет совсем»', d['absent'] == [], d)
check('пропажа кратности видна отдельно', d['undercount'] == [('100', 2, 1)], d)
d = Q.digit_diff('А 100\nБ 300', 'А 100\nБ 300\nБ 300')
check('лишний повтор виден как overcount', d['overcount'] == [('300', 1, 2)], d)
check('лишний повтор не считается пропажей', d['absent'] == [], d)
d = Q.digit_diff('А 100', 'А 100\nБ 300')
check('лишнее число — не пропажа', d['absent'] == [] and d['extra'] == ['300'], d)
d = Q.digit_diff('Итого 12 345 678', 'Итого 12345678')
check('формат записи не считается потерей', d['absent'] == [] and d['undercount'] == [], d)
d = Q.digit_diff('2024 2024 2024', '2024')
check('годы показывают число выпавших строк', d['undercount'] == [('2024', 3, 1)], d)

print('--- значимые числа ---')
check('четырёхзначное значимо', Q.significant(['1700']) == ['1700'])
check('трёхзначное не значимо', Q.significant(['240']) == [])
check('смешанный список фильтруется', Q.significant(['1', '240', '1700', '12345']) == ['1700', '12345'])

print('--- посимвольное сравнение ---')
check('одинаковый текст — сходство 1', Q.char_ratio('абв', 'абв') == 1.0)
check('разница в цифре снижает сходство', Q.char_ratio('Итого 1700', 'Итого 1710') < 1.0)
check('совпадение с точностью до пробелов', Q.char_ratio('а б в', 'абв') == 1.0)
check('совсем разные тексты — низкое сходство', Q.char_ratio('абвгд', 'яюэьы') < 0.2)

print('--- первое расхождение ---')
check('одинаковые тексты — расхождения нет', Q.first_divergence('абв', 'абв') is None)
check('различие только в пробелах по краям не считается', Q.first_divergence(' абв ', 'абв') is None)
d = Q.first_divergence('Итого 1700 руб', 'Итого 1710 руб')
check('расхождение найдено', d is not None and d[0] == 8, d)
check('фрагменты показывают число целиком',
      d is not None and '1700' in d[1] and '1710' in d[2], d)
check('разная длина при общем начале ловится', Q.first_divergence('абв', 'абвг') is not None)

print('--- вердикт ---')
def diff(absent=(), undercount=(), extra=()):
    return {'absent': list(absent), 'undercount': list(undercount),
            'extra': list(extra), 'overcount': []}


def prow(**kw):
    """одна страница с готовым разбором чисел"""
    r = row()
    r['diff'] = diff()
    r.update(kw)
    return r


v = Q.verdict([prow(), prow(page=2)])
check('чистые страницы — годится', v['ok'] and v['strict_ok'], v)
v = Q.verdict([prow(diff=diff(absent=['1700']))])
check('пропажа суммы — не годится', not v['ok'], v)
check('причина названа числом', any('1700' in r for r in v['reasons']), v['reasons'])
v = Q.verdict([prow(diff=diff(absent=['7']))])
check('пропажа короткого числа не блокирует', v['ok'], v)
check('но строгий критерий не выполнен', not v['strict_ok'], v)
check('и это сказано словами', any('строгий' in r for r in v['reasons']), v['reasons'])
v = Q.verdict([prow(diff=diff(undercount=[('2025', 19, 13)]))])
check('выпавшие строки — не годится', not v['ok'], v)
check('выпавшие строки названы', any('2025' in r for r in v['reasons']), v['reasons'])
v = Q.verdict([prow(diff=diff(undercount=[('7', 2, 1)]))])
check('нехватка короткого числа не блокирует', v['ok'], v)
v = Q.verdict([prow(diff=diff(extra=['999999']))])
check('лишнее число само по себе не блокирует', v['ok'], v)
check('но строгий критерий ломает', not v['strict_ok'], v)
v = Q.verdict([prow(truncated=True)])
check('оборванный ответ — не годится', not v['ok'], v)
check('обрыв назван причиной', any('оборван' in r for r in v['reasons']), v['reasons'])
v = Q.verdict([prow(len_pv=500)])
check('вдвое более короткий ответ — не годится', not v['ok'], v)
v = Q.verdict([prow(filtered=True)])
check('ответ, срезанный фильтром, — не годится', not v['ok'], v)
v = Q.verdict([])
check('без данных вердикта нет', not v['ok'], v)
v = Q.verdict([prow(diff=diff(absent=['1000', '2000', '3000']))])
check('несколько пропаж перечислены', len(v['reasons']) >= 1, v['reasons'])

print('--- цена ---')
pin, pout, label = Q.price_of('нет/такой-модели-в-каталоге', 'default')
check('неизвестная модель не даёт молчаливый нуль',
      (pin, pout) == (None, None) or (pin or 0) > 0, (pin, pout))

print()
print('пройдено %d, провалено %d' % (len(PASS), len(FAIL)))
if FAIL:
    print('провалы: ' + ', '.join(FAIL))
sys.exit(1 if FAIL else 0)
