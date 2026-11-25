# -*- coding: utf-8 -*-
r"""Тест отметки «нет» в своде: год без файла vs год, взятый из другого файла.

Проверяется ровно то, что было сломано:
  1. нет файла за год -> в балансовых клетках этого года стоит «нет»;
  2. ОФР/ОДДС берут ОБА года из файла-2026, поэтому при отсутствии файла-2025
     там числа, а НЕ «нет»;
  3. строки МСФО остаются пустыми, «нет» там не ставится;
  4. сборка без флага не трогает эталон xlsx.

Ловушка, из-за которой тест и написан: год в `data` — целое (`int`), а в рендере —
строка. Если сравнивать их напрямую, проверка «год есть» всегда ложна и «нет»
проставляется ВСЕМ подряд. Поэтому проверяем и положительный случай (числа есть).

Без вызовов модели. Данные — копии реальных артефактов в временном каталоге,
поэтому результат не зависит от того, что сейчас собирает пайплайн.

Запуск: python D:\models\tests\test_svod_net.py
Лог:    tests\_last_run_svod_net.txt
"""
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r'D:\models\pylibs')
sys.path.insert(0, r'D:\models')
import openpyxl
import svod_build as sb

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_svod_net.txt'), 'w',
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


def run():
    real = Path(r'D:\models\extracted')
    tmp = Path(tempfile.mkdtemp(prefix='svodnet_'))
    LOG.write(f'временный каталог: {tmp}\n')

    # ─── данные: эмитент с файлом только за 2026 и эмитент МСФО ───
    src_2026 = real / 'Финэква_6мес_2026.json'
    if not src_2026.exists():
        LOG.write('НЕТ ИСХОДНЫХ ДАННЫХ: не найден Финэква_6мес_2026.json\n')
        return tmp, None, None
    shutil.copy2(src_2026, tmp / src_2026.name)
    src_mfso = real / 'Эфферон МСФО_6мес_2026.json'
    if src_mfso.exists():
        shutil.copy2(src_mfso, tmp / src_mfso.name)

    emitters = tmp / 'emitters.json'
    emitters.write_text(json.dumps({
        'emitters': ['Финэква', 'Эфферон МСФО'],
        'orphans': [],
        'mfso': ['Эфферон МСФО'],
    }, ensure_ascii=False), encoding='utf-8')

    sb.EXTRACTED = tmp
    sb.EMITTERS_PATH = emitters
    sb.XLSX_GENERATED = tmp / 'svod.generated.xlsx'
    sb.XLSX_PATH = tmp / 'svod_ЭТАЛОН_НЕ_ТРОГАТЬ.xlsx'
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
    return tmp, ws, rows


tmp, ws, rows = run()
if ws is None:
    LOG.write('\nИТОГ: тест не выполнен — нет исходных данных\n')
    LOG.close()
    sys.exit(2)

# ─── 1. эталон не тронут ───
check('эталон xlsx не создан и не тронут', not (tmp / 'svod_ЭТАЛОН_НЕ_ТРОГАТЬ.xlsx').exists())

# ─── 2. Финэква: файла за 2025 нет ───
r = rows.get('Финэква')
check('Финэква есть в своде', r is not None)
if r:
    bal_25 = ws.cell(r, col_of('1510', '2025')).value
    bal_26 = ws.cell(r, col_of('1510', '2026')).value
    is_25 = ws.cell(r, col_of('2110', '2025')).value
    is_26 = ws.cell(r, col_of('2110', '2026')).value
    cf_25 = ws.cell(r, col_of('4100', '2025')).value

    check('баланс 2025 = «нет» (файла за 2025 нет)', bal_25 == 'нет', f'получено {bal_25!r}')
    check('баланс 2026 = число', isinstance(bal_26, (int, float)), f'получено {bal_26!r}')
    check('ОФР 2110/2025 = число из файла-2026 (НЕ «нет»)',
          isinstance(is_25, (int, float)), f'получено {is_25!r}')
    check('ОФР 2110/2026 = число', isinstance(is_26, (int, float)), f'получено {is_26!r}')
    check('ОДДС 4100/2025 = число из файла-2026 (НЕ «нет»)',
          isinstance(cf_25, (int, float)), f'получено {cf_25!r}')

    # ключевая проверка на ловушку типов: не ВСЕ клетки стали «нет»
    net_cells = sum(
        1 for c in CODES for y in ('2025', '2026')
        if ws.cell(r, col_of(c, y)).value == 'нет')
    check('«нет» стоит только в балансовых 2025 (6 клеток), а не везде',
          net_cells == len(sb.svod.BAL_CODES),
          f'получено {net_cells}, ожидалось {len(sb.svod.BAL_CODES)}')

# ─── 3. МСФО остаётся пустым ───
if 'Эфферон МСФО' in rows:
    rm = rows['Эфферон МСФО']
    vals = [ws.cell(rm, col_of(c, y)).value for c in CODES for y in ('2025', '2026')]
    check('строка МСФО пустая (не «нет»)', all(v is None for v in vals),
          f'непустых: {sum(1 for v in vals if v is not None)}')

# ─── 4. аудит объясняет разницу ───
audit = sb.AUDIT_PATH.read_text(encoding='utf-8')
check('в аудите есть раздел 2б', '## 2б' in audit)
check('аудит поясняет, что ОФР/ОДДС берутся из файла-2026',
      'ОФР/ОДДС — из файла 2026' in audit)

LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
LOG.close()
print(f'успешно {ok}, провалов {fail} (лог: tests/_last_run_svod_net.txt)')
sys.exit(1 if fail else 0)
