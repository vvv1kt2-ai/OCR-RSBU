# -*- coding: utf-8 -*-
r"""Тест состава данных: ОДДС только 4100, за прошлый год — только баланс.

Что проверяется и почему.

1. Область форм (`wanted_forms`). Отчёт текущего года — баланс, ОФР, ОДДС; отчёт прошлого
   года — ТОЛЬКО баланс: ОДДС за прошлый год берётся из сравнительной колонки отчёта
   текущего года, второй документ для этого не нужен (`pipeline.wanted_forms`, обоснование
   в её docstring). Правка 25.11.2026: здесь стояло «баланс и ОДДС», то есть docstring
   утверждал обратное тому, что проверяет assert ниже.

2. Извлечение одного кода. Полное структурирование ОДДС — самая дорогая операция конвейера:
   измерено 0.65 ₽ за вызов (1 905 вх / 34 078 вых) на «Кокс_9мес_2025». Поэтому ОДДС
   читается только до страницы с 4100 и разбирается лёгким путём. Здесь проверяется
   разбор ответа — та часть, что ломалась на реальных данных.

3. Разбор защищён от двух наблюдённых вольностей: значения приходят вперемешку с подписью
   и кодом строки, а колонки — вместе со служебными («Пояснения», «Код»).

Без сети и без денег: только чистые функции и текст источника.

Запуск: python D:\models\tests\test_data_scope.py
Лог:    tests\_last_run_scope.txt
"""
import io
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_scope.txt'), 'w',
              encoding='utf-8')
ok = fail = 0


def check(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        LOG.write(f'  OK   {name}\n')
    else:
        fail += 1
        LOG.write(f'  ПРОВАЛ {name} {detail}\n')


# ─── 1. область форм ───
check('2025: только баланс (ОДДС за прошлый год не нужен)',
      P.wanted_forms('Кокс_9мес_2025.pdf') == {'balance'},
      str(P.wanted_forms('Кокс_9мес_2025.pdf')))
check('2026: все три формы',
      P.wanted_forms('Кокс_9мес_2026.pdf') == {'balance', 'income_statement', 'cash_flow'},
      str(P.wanted_forms('Кокс_9мес_2026.pdf')))
check('правило не зависит от периода отчётности (9мес/6мес)',
      P.wanted_forms('ТГК-14_6мес_2025.pdf') == {'balance'})

# ─── 1б. отсутствие ОДДС — законно, а не пробел чтения ───
notes = P.absent_forms_note({'balance', 'income_statement', 'cash_flow'},
                            ['balance', 'income_statement'])
check('пропавший ОДДС назван допустимым отсутствием',
      len(notes) == 1 and 'отсутствует' in notes[0] and 'вправе' in notes[0], str(notes))
check('про ОДДС не сказано «не прочитано»',
      all('не прочитан' not in n for n in notes), str(notes))
check('пропавший баланс помечается без формулировки «вправе»',
      'вправе' not in P.absent_forms_note({'balance'}, [])[0])
check('все формы на месте — пометок нет',
      P.absent_forms_note({'balance'}, ['balance']) == [])

check('отсутствие ОДДС не понижает статус документа',
      P.decide_status({'balance': [True]}, [], True) == 'ok',
      P.decide_status({'balance': [True]}, [], True))
check('отсутствие ОДДС не делает документ «нет форм»',
      P.decide_status({'balance': [True]}, [], True) != 'no_forms')

# ─── 2. чистка значений ───
check('подпись и код строки отброшены, числа сохранены',
      P.cf_clean_values([None, 'Сальдо денежных потоков от текущих операций',
                         4100, -96948, 567207]) == [None, None, 4100, -96948, 567207],
      str(P.cf_clean_values([None, 'Сальдо денежных потоков от текущих операций',
                             4100, -96948, 567207])))
check('скобки означают минус',
      P.cf_clean_values(['(123)', '1 234', '—']) == [-123, 1234, None],
      str(P.cf_clean_values(['(123)', '1 234', '—'])))
check('числа остаются числами',
      P.cf_clean_values([-5, 0, 7.5]) == [-5, 0, 7.5])

# ─── 3. выравнивание колонок ───
COLS_BAD = ['Пояснения', 'Наименование показателя', 'Код',
            'За 9 месяцев 2026 г.', 'За 9 месяцев 2025 г.']
VALS_BAD = [None, None, 4100, -96948, 567207]
cols, vals = P.cf_period_columns(COLS_BAD, VALS_BAD)
check('служебные колонки сняты', cols == ['За 9 месяцев 2026 г.', 'За 9 месяцев 2025 г.'],
      str(cols))
check('значения сдвинуты вместе с колонками', vals == [-96948, 567207], str(vals))

COLS_OK = ['За Январь-Сентябрь 2026 г.', 'За Январь-Сентябрь 2025 г.']
VALS_OK = [-2781556, -20956104]
check('корректный ответ не портится',
      P.cf_period_columns(COLS_OK, VALS_OK) == (COLS_OK, VALS_OK))

# ─── 4. правило статуса: урезанная форма не делает документ «на проверку» ───
src = io.open(os.path.join(r'D:\models', 'pipeline.py'), encoding='utf-8').read()
check('в process() урезанные формы исключены из вердикта',
      "if form_obj.get('scope')" in src)
check('урезанная форма не добирается страницами ради 4500',
      "if not d or d.get('scope')" in src)
check('урезанная форма не отбрасывается фильтром «нет таблицы»',
      "в урезанном составе не найден код" in src)
check('ОДДС читается не дальше страницы с 4100',
      'CF_KEEP_CODES' in src and 'CF_PAGE_CAP' in src)

# ─── 4б. свод не считает урезанный ОДДС провалом ───
# Найдено 19.11.2026: правило `4100 == 4110-4120` при отсутствии 4110/4120 подставляло нули
# и объявляло провал на верных данных — по два ложных провала на каждый документ с 4100-only.
import svod

def cf_form(vals):
    return {'items': [{'code': '4100', 'values': vals}], 'columns': ['a', 'b']}

check('из ОДДС извлекаются оба кода: 4100 и 4110',
      P.CF_KEEP_CODES == ('4100', '4110'), str(P.CF_KEEP_CODES))
check('останов чтения ОДДС привязан к 4100, а не к 4110',
      "if cf_partial and '4100' in re.sub" in io.open(
          os.path.join(r'D://models', 'pipeline.py'), encoding='utf-8').read())

check('урезанный ОДДС (только 4100) не даёт провалов свода',
      svod.check_cf(cf_form([-100, -200])) == [],
      str(svod.check_cf(cf_form([-100, -200]))))

full_ok = {'items': [{'code': '4100', 'values': [100]},
                     {'code': '4110', 'values': [100]},
                     {'code': '4120', 'values': [0]}], 'columns': ['a']}
check('полная форма с верными числами не даёт провалов',
      svod.check_cf(full_ok) == [], str(svod.check_cf(full_ok)))

full_bad = {'items': [{'code': '4100', 'values': [100]},
                      {'code': '4110', 'values': [90]},
                      {'code': '4120', 'values': [0]}], 'columns': ['a']}
check('реальное расхождение по-прежнему ловится',
      len(svod.check_cf(full_bad)) == 1, str(svod.check_cf(full_bad)))

# ─── 4в. ранний останов детекции ───
# Формы стоят в начале, пояснения занимают десятки страниц: в 49-страничном отчёте формы
# кончаются на 11-й. Останов разрешён только когда все нужные формы найдены.
S = P.should_stop_detection
check('останов, когда все формы найдены и прошли 4 страницы без форм',
      S({'balance', 'cash_flow', 'income_statement'},
        {'balance', 'cash_flow', 'income_statement'}, 11, 16) is True)
check('не останов, если найдены не все нужные формы',
      S({'balance', 'cash_flow', 'income_statement'}, {'balance'}, 2, 40) is False)
check('не останов, если запас меньше 4 страниц',
      S({'balance'}, {'balance'}, 2, 5) is False)
check('не останов, если форм ещё не нашли',
      S({'balance'}, set(), 0, 8) is False)
check('останов не зависит от лишних найденных форм',
      S({'balance'}, {'balance', 'notes'}, 2, 8) is True)

# ─── 5. кэш извлечения привязан к версии подсказки ───
check('метка кэша содержит версию подсказки',
      'cf4100_v' in src and 'CF_PROMPT_VERSION' in src)

LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
LOG.close()
print(f'успешно {ok}, провалов {fail} (лог: tests/_last_run_scope.txt)')
sys.exit(1 if fail else 0)