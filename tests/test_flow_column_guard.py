# -*- coding: utf-8 -*-
r"""Тест предохранителя: свод НЕ ставит числа формы в год, который не доказан.

Что было сломано:
  ОДДС трёх документов-2026 получил заголовки колонок от ЧУЖОЙ формы —
  ['2025-06-30', '2025-12-31']. Колонки «2026» в заголовках нет вообще, а
  `col_index_flow(cf, 2025)` находил первую колонку. Свод молча писал в клетку
  2025 число 2026 года: у «Бианка премиум» 4100/2025 = −9514 вместо −85040,
  а 4100/2026 оставался пустым. Ошибка выглядела как данные.

Правило, которое проверяется: ОФР/ОДДС берутся из файла-2026 обеими колонками,
поэтому колонка СВОЕГО года обязана найтись. Нет её — не доказана и колонка
прошлого года, и брать оттуда число нельзя. Пусто + запись в аудите.

Проверяется и обратное: где колонки на месте, числа обязаны быть (иначе
предохранитель «починил» бы всё подряд, как когда-то правило «нет»).

Без вызовов модели. Данные синтетические, в временном каталоге.

Запуск: python D:\models\tests\test_flow_column_guard.py
Лог:    tests\_last_run_flow_guard.txt
"""
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r'D:\models\pylibs')
sys.path.insert(0, r'D:\models')
import openpyxl
import svod
import svod_build as sb

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_flow_guard.txt'), 'w',
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


CODES = ['2110', '2300', '2330', '2320', '1510', '1550', '1410', '1450',
         '1250', '1300', '4100', '4110']


def col_of(code, year):
    return 2 + CODES.index(code) * 2 + (1 if year == '2026' else 0)


CF_BAD = ['2025-06-30', '2025-12-31']            # заголовок чужой формы (замер)
CF_GOOD = ['За 1 полугодие 2026 г.', 'За 1 полугодие 2025 г.']
CF_ONE = ['За 1 полугодие 2026 г.']              # одна колонка — законный случай
IS_GOOD = ['За 1 полугодие 2026 г.', 'За 1 полугодие 2025 г.']
IS_BAD = ['За 1 полугодие 2025 г.', 'За 1 полугодие 2024 г.']


def art(cf_cols, is_cols, bal=True):
    """Артефакт-2026 с заданными заголовками колонок."""
    d = {
        'schema_version': 1,
        'source': {'file': 'Тест_6мес_2026.pdf', 'text_layer': True},
        'company': {'name': 'Тест'},
        'checks': [],
        'warnings': [],
        'status': 'ok',
        'income_statement': {
            'form': '0710002', 'columns': list(is_cols),
            'items': [{'code': '2110', 'name': 'Выручка', 'values': [1000, 900]}]},
        'cash_flow': {
            'form': '0710005', 'columns': list(cf_cols),
            'items': [{'code': '4100', 'name': 'Сальдо', 'values': [111, 222]},
                      {'code': '4110', 'name': 'Поступления', 'values': [333, 444]}]},
    }
    if bal:
        d['balance'] = {
            'form': '0710001',
            'columns': ['На 30 июня 2026 г.', 'На 31 декабря 2025 г.', 'На 31 декабря 2024 г.'],
            'items': [{'code': '1510', 'name': 'Заемные средства', 'values': [100, 90, 80]}]}
    return d


# ─── 1. col_index_flow: заголовок без года не находится ───
LOG.write('=== 1. col_index_flow ===\n')
check('год в заголовке находится',
      svod.col_index_flow({'columns': CF_GOOD}, 2026) == 0,
      f'получено {svod.col_index_flow({"columns": CF_GOOD}, 2026)}')
check('прошлый год находится',
      svod.col_index_flow({'columns': CF_GOOD}, 2025) == 1,
      f'получено {svod.col_index_flow({"columns": CF_GOOD}, 2025)}')
check('чужой заголовок НЕ даёт колонку 2026',
      svod.col_index_flow({'columns': CF_BAD}, 2026) is None,
      f'получено {svod.col_index_flow({"columns": CF_BAD}, 2026)}')
check('чужой заголовок ошибочно даёт колонку 2025 (та самая ловушка)',
      svod.col_index_flow({'columns': CF_BAD}, 2025) == 0)

# ─── 2. предохранитель в исходнике ───
LOG.write('\n=== 2. предохранитель объявлен в svod.py ===\n')
src = io.open(r'D:\models\svod.py', encoding='utf-8').read()
check('в svod.py есть проверка «колонки не называют год»',
      'колонки {form_ru} не называют {year} год' in src)

# ─── 3. сборка свода ───
tmp = Path(tempfile.mkdtemp(prefix='flowguard_'))
LOG.write(f'\n=== 3. сборка свода во временном каталоге {tmp} ===\n')

json.dump(art(CF_BAD, IS_GOOD), open(tmp / 'Кривой_6мес_2026.json', 'w', encoding='utf-8'),
          ensure_ascii=False)
json.dump(art(CF_GOOD, IS_GOOD), open(tmp / 'Целый_6мес_2026.json', 'w', encoding='utf-8'),
          ensure_ascii=False)
json.dump(art(CF_ONE, IS_GOOD), open(tmp / 'ОднаКолонка_6мес_2026.json', 'w', encoding='utf-8'),
          ensure_ascii=False)
json.dump(art(CF_GOOD, IS_BAD), open(tmp / 'КривойОФР_6мес_2026.json', 'w', encoding='utf-8'),
          ensure_ascii=False)

emitters = tmp / 'emitters.json'
emitters.write_text(json.dumps({
    'emitters': ['Кривой', 'Целый', 'ОднаКолонка', 'КривойОФР'],
    'orphans': [], 'mfso': [],
}, ensure_ascii=False), encoding='utf-8')

sb.EXTRACTED = tmp
sb.EMITTERS_PATH = emitters
sb.XLSX_GENERATED = tmp / 'svod.generated.xlsx'
sb.XLSX_PATH = tmp / 'ЭТАЛОН_НЕ_ТРОГАТЬ.xlsx'
sb.CSV_PATH = tmp / 'svod.csv'
sb.AUDIT_PATH = tmp / 'svod_audit.md'
sb.main(overwrite_gold=False)

wb = openpyxl.load_workbook(sb.XLSX_GENERATED)
ws = wb.active
rows = {}
for r in range(3, ws.max_row + 1):
    v = ws.cell(r, 1).value
    if v:
        rows[str(v)] = r
audit = sb.AUDIT_PATH.read_text(encoding='utf-8')


def cell(em, code, year):
    return ws.cell(rows[em], col_of(code, year)).value


# ─── 4. кривой ОДДС: ни одного числа ───
LOG.write('\n=== 4. ОДДС с чужим заголовком ===\n')
check('Кривой есть в своде', 'Кривой' in rows)
if 'Кривой' in rows:
    vals = [cell('Кривой', c, y) for c in ('4100', '4110') for y in ('2025', '2026')]
    check('ни одна клетка ОДДС не заполнена', all(v is None for v in vals),
          f'получено {vals}')
    check('в частности 4100/2025 пуст (а не −9514 в году 2026)',
          cell('Кривой', '4100', '2025') is None,
          f'получено {cell("Кривой", "4100", "2025")!r}')
    check('в частности 4100/2026 пуст', cell('Кривой', '4100', '2026') is None,
          f'получено {cell("Кривой", "4100", "2026")!r}')
    check('баланс при этом прочитан (предохранитель не гасит всё)',
          isinstance(cell('Кривой', '1510', '2026'), (int, float)),
          f'получено {cell("Кривой", "1510", "2026")!r}')
    check('ОФР при этом прочитан (он в этом артефакте целый)',
          isinstance(cell('Кривой', '2110', '2026'), (int, float)),
          f'получено {cell("Кривой", "2110", "2026")!r}')
    check('аудит объясняет, что колонки не называют год',
          'не называют 2026 год' in audit and 'ОДДС' in audit)

# ─── 5. целый ОДДС: числа на месте ───
LOG.write('\n=== 5. ОДДС с правильным заголовком (положительный случай) ===\n')
if 'Целый' in rows:
    check('4100/2026 = 111 (первая колонка)',
          cell('Целый', '4100', '2026') == 111,
          f'получено {cell("Целый", "4100", "2026")!r}')
    check('4100/2025 = 222 (вторая колонка)',
          cell('Целый', '4100', '2025') == 222,
          f'получено {cell("Целый", "4100", "2025")!r}')
    check('4110/2026 = 333', cell('Целый', '4110', '2026') == 333,
          f'получено {cell("Целый", "4110", "2026")!r}')

# ─── 6. одна колонка: не переусердствовать ───
LOG.write('\n=== 6. ОДДС с одной колонкой ===\n')
if 'ОднаКолонка' in rows:
    check('4100/2026 = 111 (колонка есть)', cell('ОднаКолонка', '4100', '2026') == 111,
          f'получено {cell("ОднаКолонка", "4100", "2026")!r}')
    check('4100/2025 пуст (колонки нет — и это не ошибка)',
          cell('ОднаКолонка', '4100', '2025') is None,
          f'получено {cell("ОднаКолонка", "4100", "2025")!r}')

# ─── 7. кривой ОФР: та же защита ───
LOG.write('\n=== 7. ОФР с чужим заголовком ===\n')
if 'КривойОФР' in rows:
    vals = [cell('КривойОФР', c, y) for c in ('2110', '2300') for y in ('2025', '2026')]
    check('ни одна клетка ОФР не заполнена', all(v is None for v in vals), f'получено {vals}')
    check('ОДДС при этом прочитан (защита по каждой форме своя)',
          cell('КривойОФР', '4100', '2026') == 111,
          f'получено {cell("КривойОФР", "4100", "2026")!r}')
    check('аудит называет ОФР',
          'заголовки колонок не называют год документа' in audit
          and any('| КривойОФР |' in l and 'ОФР' in l for l in audit.splitlines()),
          'в аудите нет строки про ОФР')

# ─── 8. эталон не тронут ───
check('эталон xlsx не создан', not (tmp / 'ЭТАЛОН_НЕ_ТРОГАТЬ.xlsx').exists())

LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
LOG.close()
print(f'успешно {ok}, провалов {fail} (лог: tests/_last_run_flow_guard.txt)')
sys.exit(1 if fail else 0)
