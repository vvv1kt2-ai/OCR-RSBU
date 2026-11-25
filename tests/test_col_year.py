# -*- coding: utf-8 -*-
r"""Тест сопоставления колонки с годом: пробел ВНУТРИ года не должен её терять.

Дефект: `col_index_flow` искал год непрерывной подстрокой (`'2026' in column`). Транскрипция
иногда отдаёт «За 1 полугод 20 26 г.» — пробел внутри числа. Такая колонка не находилась,
индекс становился None, и значения молча не попадали в свод.

Замер: `ИПС_6мес_2026`, ОДДС, колонки `['За 1 полугод 20 26 г.', 'За год 20 25 г.']`.
В артефакте есть 4100 = [-1932, -93167] и 4110, и в эталоне свода эти числа ЕСТЬ
(4100/2026 = -1932, 4100/2025 = -93167), а генерируемый свод оставлял 4 клетки пустыми.
После правки потерянных чисел стало 2 вместо 6 (остались случаи с иной причиной).

Без вызовов модели. Запуск: python D:\models\tests\test_col_year.py
Лог:    tests\_last_run_col_year.txt
"""
import io
import json
import os
import sys

sys.path.insert(0, r'D:\models')
import svod

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_col_year.txt'), 'w',
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


def form(cols):
    return {'columns': cols, 'items': []}


# ─── 1. обычные заголовки ───
check('нормальный заголовок 2026 -> 0',
      svod.col_index_flow(form(['За полугодие 2026 г.', 'За полугодие 2025 г.']), 2026) == 0)
check('нормальный заголовок 2025 -> 1',
      svod.col_index_flow(form(['За полугодие 2026 г.', 'За полугодие 2025 г.']), 2025) == 1)
check('ISO-колонка 2026-06-30 -> 0',
      svod.col_index_flow(form(['2026-06-30', '2025-12-31']), 2026) == 0)

# ─── 2. пробел внутри года (измеренный случай) ───
BROKEN = ['За 1 полугод 20 26 г.', 'За год 20 25 г.']
check('пробел внутри года: 2026 -> 0 (был None)',
      svod.col_index_flow(form(BROKEN), 2026) == 0,
      f'получено {svod.col_index_flow(form(BROKEN), 2026)!r}')
check('пробел внутри года: 2025 -> 1',
      svod.col_index_flow(form(BROKEN), 2025) == 1,
      f'получено {svod.col_index_flow(form(BROKEN), 2025)!r}')

# ─── 3. ложных срабатываний быть не должно ───
check('колонка чужого года не подходит: 2026 при наличии только 2025 -> None',
      svod.col_index_flow(form(['За год 20 25 г.']), 2026) is None)
check('колонка чужого года не подходит: 2025 при наличии только 2026 -> None',
      svod.col_index_flow(form(['За полугодие 2026 г.']), 2025) is None)
check('2025-06-30 не опознаётся как 2026',
      svod.col_index_flow(form(['2025-06-30', '2025-12-31']), 2026) is None)

# ─── 4. баланс: тот же пробел в годе ───
check('баланс: «На 30 Июня 2026 г.» -> 0',
      svod.col_index_balance(form(['На 30 Июня 2026 г.', 'На 31 Декабря 2025 г.']), 2026) == 0)
check('баланс: пробел внутри года «На 30 Июня 20 26 г.» -> 0',
      svod.col_index_balance(form(['На 30 Июня 20 26 г.']), 2026) == 0,
      f'получено {svod.col_index_balance(form(["На 30 Июня 20 26 г."]), 2026)!r}')
check('баланс: не июньская колонка не подходит',
      svod.col_index_balance(form(['На 31 Декабря 2026 г.']), 2026) is None)

# ─── 5. вырожденные входы не падают ───
check('пустая форма -> None', svod.col_index_flow(form([]), 2026) is None)
check('None вместо формы -> None', svod.col_index_flow(None, 2026) is None)
check('баланс: None вместо формы -> None', svod.col_index_balance(None, 2026) is None)
check('колонка не строка (число) не падает',
      svod.col_index_flow(form([2026, 2025]), 2026) == 0)

# ─── 6. проверка на реальном артефакте, если он есть ───
p = os.path.join(r'D:\models\extracted', 'ИПС_6мес_2026.json')
if os.path.exists(p):
    d = json.load(open(p, encoding='utf-8'))
    cf = d.get('cash_flow') or {}
    check('реальный ИПС_6мес_2026: ОДДС 2026 -> 0',
          svod.col_index_flow(cf, 2026) == 0,
          f"колонки {cf.get('columns')}")
    check('реальный ИПС_6мес_2026: ОДДС 2025 -> 1',
          svod.col_index_flow(cf, 2025) == 1)
else:
    LOG.write('  (артефакт ИПС_6мес_2026 отсутствует — проверки на реальных данных пропущены)\n')

LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
LOG.close()
print(f'успешно {ok}, провалов {fail} (лог: tests/_last_run_col_year.txt)')
sys.exit(1 if fail else 0)
