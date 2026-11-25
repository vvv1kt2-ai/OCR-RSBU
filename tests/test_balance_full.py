# -*- coding: utf-8 -*-
r"""Тест выгрузки полного баланса: _balance_full.py -> xlsx + md.

Зачем тест на разовый отчёт. У этого скрипта за один вечер нашлись ТРИ дефекта, и ни один
не был виден в консоли — все три жили в самом файле, который читает человек:

  1. блок невязок в MD собирался поштучными insert(8, …) в цикле: строки невязок
     переворачивались, а закрывающая фраза «Всё остальное сходится» вставала МЕЖДУ ними
     («Денум» выше фразы, «ЕнисейАгроСоюз» ниже);
  2. лист «Главное» не вставал первым: сдвиг считался от числа листов, при шести листах
     выходило -5 и позиция -1, а insert(-1, …) вставляет ПРЕД последним;
  3. заголовок листа писался циклом range(4) на фиксированное число колонок, поэтому у
     баланса с тремя колонками заголовок ТРЕТЬЕЙ колонки оставался пустым — данные были,
     а шапки над ними нет.

Проверяется именно это: форма выдачи, а не арифметика (арифметика — в _balance_full.py
и сверена с отчётами вручную).

Скрипт перезапускается тестом, чтобы проверялся генератор, а не только готовый файл.
Вызовов модели нет.

Запуск: python D:\models\tests\test_balance_full.py
Лог:    tests\_last_run_balance_full.txt
"""
import io
import os
import re
import subprocess
import sys

sys.path.insert(0, r'D:\models\pylibs')
sys.path.insert(0, r'D:\models')
import openpyxl

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_balance_full.txt'), 'w',
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


XLSX = r'D:\models\extracted\balance_full_ЕнисейАгроСоюз_Денум.xlsx'
MD = r'D:\models\extracted\balance_full_анализ.md'

# ─── 0. пересобрать выдачу ───
LOG.write('=== 0. пересборка выдачи ===\n')
r = subprocess.run([sys.executable, r'D:\models\_balance_full.py'],
                   capture_output=True, text=True, cwd=r'D:\models')
check('генератор отработал без ошибки', r.returncode == 0,
      (r.stderr or '')[-300:])
check('в консоли ровно две невязки вне допуска',
      len(re.findall(r'^\s+\S.*?: \S', r.stdout, re.M)) == 2, r.stdout[-300:])

if not (os.path.exists(XLSX) and os.path.exists(MD)):
    check('выдача на месте', False, f'{XLSX} / {MD}')
    LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
    LOG.close()
    print(f'успешно {ok}, провалов {fail}')
    sys.exit(1)

wb = openpyxl.load_workbook(XLSX)
md = io.open(MD, encoding='utf-8').read()

# ─── 1. лист «Главное» — первым ───
LOG.write('\n=== 1. лист «Главное» первым ===\n')
check('«Главное» — первый лист', wb.sheetnames[0] == 'Главное', f'{wb.sheetnames}')
check('«Главное» открывается по умолчанию', wb.active.title == 'Главное',
      wb.active.title)
check('есть лист на каждый документ',
      all(s in wb.sheetnames for s in
          ('ЕнисейАгроСоюз 2026', 'ЕнисейАгроСоюз 2025', 'Денум 2026', 'Денум 2025')),
      f'{wb.sheetnames}')

# ─── 2. шапка листа: все колонки отчёта подписаны ───
LOG.write('\n=== 2. шапка листа ===\n')
for name in ('ЕнисейАгроСоюз 2026', 'ЕнисейАгроСоюз 2025', 'Денум 2026', 'Денум 2025'):
    ws = wb[name]
    head = [ws.cell(4, c).value for c in range(1, ws.max_column + 1)]
    check(f'{name}: первые две шапки на месте',
          head[0] == 'Код' and head[1] == 'Наименование', f'{head}')
    data_cols = [h for h in head if h and h.startswith('На ')]
    check(f'{name}: подписаны ВСЕ три колонки отчёта', len(data_cols) == 3,
          f'{head}')

# ─── 3. блок невязок в MD собран целиком ───
LOG.write('\n=== 3. блок невязок в MD ===\n')
i = md.find('| Эмитент | Год | Итог | Колонка |')
# Ищем вместе с открывающими «**»: иначе граница блока попадает ВНУТРЬ выделения и в
# блок заезжает хвост «**» от фразы, которую он как раз должен отсекать.
j = md.find('**Всё остальное сходится')
check('таблица невязок найдена', i >= 0 and j > i, f'i={i} j={j}')
block = md[i:j]
rows = [ln for ln in block.splitlines() if ln.startswith('| ') and '---' not in ln]
check('в таблице шапка и ДВЕ строки невязок', len(rows) == 3, f'{rows}')
check('обе невязки выше закрывающей фразы',
      'ЕнисейАгроСоюз' in block and 'Денум' in block)
check('между строками невязок нет постороннего текста',
      all(ln.startswith('|') or not ln.strip() for ln in block.splitlines()),
      repr(block[-200:]))

# ─── 4. сами невязки: ровно те две, и с верной разницей ───
LOG.write('\n=== 4. содержание невязок ===\n')
check('ЕнисейАгроСоюз 2026: 1200, колонка 2024, разница 30',
      bool(re.search(r'ЕнисейАгроСоюз \| 2026 \| 1200 .*2024.*1 060 166 \| 1 060 136 '
                     r'\| \*\*30\*\*', block)), repr(block[:400]))
check('Денум 2026: 1600 АКТИВ = ПАССИВ, колонка 2025, разница -4',
      bool(re.search(r'Денум \| 2026 \| 1600 АКТИВ = ПАССИВ \| На 31 декабря 2025 г\. '
                     r'\| 2 145 305 \| 2 145 309 \| \*\*-4\*\*', block)),
      repr(block[:400]))

# ─── 5. лист «Главное»: те же две строки ───
LOG.write('\n=== 5. лист «Главное» ===\n')
ws0 = wb['Главное']
hdr_row = None
for r_ in range(1, ws0.max_row + 1):
    if ws0.cell(r_, 1).value == 'Эмитент':
        hdr_row = r_
        break
check('шапка таблицы найдена', hdr_row is not None)
data = []
if hdr_row:
    for r_ in range(hdr_row + 1, ws0.max_row + 1):
        if ws0.cell(r_, 1).value:
            data.append([ws0.cell(r_, c).value for c in range(1, 8)])
check('в «Главном» ровно две строки', len(data) == 2, f'{data}')
check('первая строка — ЕнисейАгроСоюз, разница 30',
      data and data[0][0] == 'ЕнисейАгроСоюз' and data[0][6] == 30, f'{data[:1]}')
check('вторая строка — Денум, разница -4',
      len(data) > 1 and data[1][0] == 'Денум' and data[1][6] == -4, f'{data[1:]}')

# ─── 6. полный баланс действительно полный ───
LOG.write('\n=== 6. полнота баланса ===\n')
ws = wb['ЕнисейАгроСоюз 2025']
codes = [str(ws.cell(r_, 1).value) for r_ in range(5, ws.max_row + 1)]
check('в листе есть итог 1600', '1600' in codes, f'{codes[:5]}…')
check('в листе есть 1520', '1520' in codes)
check('в листе есть 1700', '1700' in codes)
r1520 = codes.index('1520') + 5 if '1520' in codes else 0
if r1520:
    check('1520 = 380 843 (напечатано 369 996 + аренда 10 847)',
          ws.cell(r1520, 3).value == 380843, f'{ws.cell(r1520, 3).value}')
    kids = [ws.cell(r_, 2).value for r_ in range(r1520 + 1, r1520 + 4)]
    check('расшифровки 1520 выгружены с отступом',
          any(k and k.startswith('    ') for k in kids), f'{kids}')

# ─── 7. раздел про аренду ───
LOG.write('\n=== 7. раздел про аренду ===\n')
check('в MD есть раздел про аренду', '## Отдельно: строка аренды' in md)
check('в разделе сказано, что баланс от дубля не страдает',
      'не входит ни в один итог' in md)
check('в MD аренда ЕнисейАгроСоюза за 2025 = 10 847',
      bool(re.search(r'\| ЕнисейАгроСоюз \| 2025 \|.*\| 10 847 \|', md)))
check('в XLSX есть лист «Аренда»', 'Аренда' in wb.sheetnames)

LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
LOG.close()
print(f'успешно {ok}, провалов {fail} (лог: tests/_last_run_balance_full.txt)')
sys.exit(1 if fail else 0)
