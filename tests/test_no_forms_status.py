# -*- coding: utf-8 -*-
r"""Тест правила «сбой структурирования — не отсутствие форм».

Проверяется ровно то, что было сломано: документ с реальным балансом получал статус
`no_forms`, если структурирование формы упало по 502/503. `no_forms` — утверждение о
СОДЕРЖИМОМ документа, сбой вызова — о ЧТЕНИИ; для свода разница критична, потому что по
`no_forms` он показал бы пустые клетки там, где отчётность есть.

Замер: `Биовитрум_6мес_2025` — баланс найден, структурирование упало с HTTP 503
«Все каналы поставки этой модели временно недоступны», статус был `no_forms`.

Без вызовов модели. Запуск: python D:\models\tests\test_no_forms_status.py
Лог:    tests\_last_run_no_forms.txt
"""
import io
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_no_forms.txt'), 'w',
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


# Точный текст пометки из артефакта Биовитрум_6мес_2025 (измерено, не придумано).
REAL_WARN = ('balance: whole-form structure failed (LLM failed after retries: HTTP 503: '
             'b\'{"error":{"message":"\\u0412\\u0441\\u0435 \\u043a\\u0430\\u043d\\u0430\\u043b'
             '\\u044b \\u043f\\u043e\\u0441\\u0442\\u0430\\u0432\\u043a\\u0438 \\u044d\\u0442'
             '\\u043e\\u0439 \\u043c\\u043e\\u0434\\u0435\\u043b\\u0438 \\u0432\\u0440\\u0435'
             '\\u043c\\u0435\\u043d\\u043d\\u043e \\u043d\\u0435\\u0434\\u043e\\u0441\\u0442'
             '\\u0443\\u043f\\u043d\\u044b"}}\')')

# ─── 1. сбой структурирования понижает no_forms ───
check('no_forms + сбой целой формы -> incomplete',
      P.downgrade_no_forms('no_forms', [REAL_WARN]) == 'incomplete',
      f"получено {P.downgrade_no_forms('no_forms', [REAL_WARN])!r}")

check('no_forms + сбой разбиения на части -> incomplete',
      P.downgrade_no_forms('no_forms', ['balance: split structuring failed: timeout']) == 'incomplete')

check('no_forms + сбой среди прочих пометок -> incomplete',
      P.downgrade_no_forms('no_forms', ['что-то ещё', REAL_WARN, 'и ещё']) == 'incomplete')

# ─── 2. честное «форм нет» не трогаем ───
check('no_forms без маркера сбоя остаётся no_forms',
      P.downgrade_no_forms('no_forms', ['no target forms found in document']) == 'no_forms')
check('no_forms с пустыми пометками остаётся no_forms',
      P.downgrade_no_forms('no_forms', []) == 'no_forms')
check('no_forms с None вместо пометок остаётся no_forms',
      P.downgrade_no_forms('no_forms', None) == 'no_forms')

# ─── 3. прочие статусы не меняются ───
for st in ('ok', 'needs_review', 'incomplete'):
    check(f'{st} не меняется даже при маркере сбоя',
          P.downgrade_no_forms(st, [REAL_WARN]) == st,
          f'получено {P.downgrade_no_forms(st, [REAL_WARN])!r}')

# ─── 4. маркеры совпадают с тем, что реально пишет код ───
# Если текст пометки в scan_pipeline переименуют, правило тихо перестанет срабатывать.
src = io.open(os.path.join(r'D:\models', 'pipeline.py'), encoding='utf-8').read()
for m in P.STRUCTURE_FAILED_MARKERS:
    check(f'маркер {m!r} есть в тексте pipeline.py', m in src)

# ─── 4б. сбой ЧТЕНИЯ страницы — тоже не «форм нет» ───
# Замер 02.11.2026 на новых отчётах: при полном отказе сети (502 на каждой странице)
# документ возвращался с status=no_forms, хотя формы в нём есть и страницы были выбраны
# детекцией. Маркер «чтение не удалось» добавлен в STRUCTURE_FAILED_MARKERS именно за этим.
READ_FAIL_WARN = ('страница 1: чтение не удалось (<urlopen error Tunnel connection failed: '
                  '502 Bad Gateway>) — строки этой страницы в форме отсутствуют')
check('no_forms + сбой ЧТЕНИЯ страницы -> incomplete',
      P.downgrade_no_forms('no_forms', [READ_FAIL_WARN]) == 'incomplete',
      f'получено {P.downgrade_no_forms("no_forms", [READ_FAIL_WARN])!r}')
check('маркер сбоя чтения входит в список',
      'чтение не удалось' in P.STRUCTURE_FAILED_MARKERS)

# ─── 5. правило действительно подключено к process() ───
check('process() вызывает downgrade_no_forms', 'downgrade_no_forms(result[' in src)

LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
LOG.close()
print(f'успешно {ok}, провалов {fail} (лог: tests/_last_run_no_forms.txt)')
sys.exit(1 if fail else 0)
