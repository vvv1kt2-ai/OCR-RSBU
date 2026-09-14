# -*- coding: utf-8 -*-
"""
_diff_gold.py - Compare pipeline-generated svod_2025_2026.csv with human-corrected svod_2025_2026.xlsx.
Enumerate every differing cell, classify the difference, and trace back to the source JSON.
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, 'D:/models/pylibs')
sys.path.insert(0, 'D:/models')
import openpyxl
import svod

EXTRACTED = Path('D:/models/extracted')
CSV_PATH = EXTRACTED / 'svod_2025_2026.csv'
XLSX_PATH = EXTRACTED / 'svod_2025_2026.xlsx'

CODES = ['2110', '2300', '2330', '2320', '1510', '1550', '1410', '1450', '1250', '1300', '4100', '4110']
FORM_OF = {
    '2110': 'OFR', '2300': 'OFR', '2330': 'OFR', '2320': 'OFR',
    '1510': 'bal', '1550': 'bal', '1410': 'bal', '1450': 'bal',
    '1250': 'bal', '1300': 'bal',
    '4100': 'ODDS', '4110': 'ODDS',
}

# CSV column name -> canonical (year, code) mapping
# CSV uses "1550+аренда_2025" but the underlying code is "1550"
def csv_col_to_code(csv_col_name):
    """Map CSV column header like '1450+аренда_2025' -> ('2025', '1450')."""
    # Remove +ar part if present
    base = csv_col_name.replace('+аренда', '')
    parts = base.rsplit('_', 1)
    if len(parts) == 2:
        return (parts[1], parts[0])
    return ('?', csv_col_name)

EMITTERS = [
    'ТГК-14', 'КИФА', 'Проект 111', 'Афанасий', 'Омега', 'Байсэл',
    'Бианка премиум', 'Сибсульфур', 'Простая еда', 'Славянск ЭКО',
    'НовосибирскАвтодор', 'Моторные технологии', 'Эфферон', 'Эфферон МСФО',
    'Нижегородец Восток', 'Финэква', 'Органик парк', 'ИПС',
    'Артген (ИСКЧ) МСФО', 'Артген (ИСКЧ)', 'Смартфакт', 'КЛВЗ Кристалл',
]
ORPHANS = ['Корпсан', 'Рекорд трейд']
ALL_EMITTERS = EMITTERS + ORPHANS
LEGEND_ROWS = {'Обозначения:', 'Единица измерения:'}


def parse_csv():
    """Parse the CSV into {emitter: {(year, code): value_str}}."""
    data = {}
    with open(CSV_PATH, encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        header = next(reader)
        col_map = []  # list of (year, code) for each data column
        for col_name in header[1:]:
            col_map.append(csv_col_to_code(col_name.strip()))
        for row in reader:
            if not row or not row[0].strip():
                continue
            emitter = row[0].strip()
            cells = {}
            for i, (year, code) in enumerate(col_map):
                val_str = row[i + 1].strip() if i + 1 < len(row) else ''
                cells[(year, code)] = val_str
            data[emitter] = cells
    return data, col_map


def parse_xlsx():
    """Parse the XLSX into {emitter: {(year, code): numeric_or_str_or_None}}."""
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    print('XLSX sheets:', wb.sheetnames)
    for sn in wb.sheetnames:
        ws = wb[sn]
        print(f'  Sheet "{sn}": {ws.max_row} rows x {ws.max_column} cols')

    ws = wb['Свод']
    # Build col_map: col_idx -> (year, code)
    col_map = {}
    for ci, code in enumerate(CODES):
        col_start = 2 + ci * 2
        y25 = str(ws.cell(2, col_start).value).strip() if ws.cell(2, col_start).value else '2025'
        y26 = str(ws.cell(2, col_start + 1).value).strip() if ws.cell(2, col_start + 1).value else '2026'
        col_map[col_start] = (y25, code)
        col_map[col_start + 1] = (y26, code)

    data = {}
    for row_idx in range(3, ws.max_row + 1):
        emitter_val = ws.cell(row_idx, 1).value
        if not emitter_val:
            continue
        emitter = str(emitter_val).strip()
        if emitter in LEGEND_ROWS or emitter.startswith('Обозначения') or emitter.startswith('Единица'):
            continue
        cells = {}
        for col_idx, (year, code) in col_map.items():
            val = ws.cell(row_idx, col_idx).value
            cells[(year, code)] = val
        data[emitter] = cells
    return data


def norm_num(v):
    """Normalize value to comparable form."""
    if v is None or v == '' or v == 'None':
        return None
    if isinstance(v, str):
        v = v.strip()
        if v == '' or v == '\u043d\u0435\u0442':  # "нет"
            return v if v == '\u043d\u0435\u0442' else None
        # Strip non-breaking spaces etc.
        v2 = v.replace('\xa0', '').replace(' ', '').replace(',', '.')
        try:
            return float(v2)
        except ValueError:
            return v
    return float(v)


def classify_difference(csv_val_str, xlsx_val):
    """Classify the difference between CSV (string) and XLSX (native)."""
    cs = csv_val_str.strip() if csv_val_str else ''
    csv_n = norm_num(cs)
    xlsx_n = norm_num(xlsx_val)

    if csv_n is None and xlsx_n is None:
        return None

    csv_is_num = isinstance(csv_n, (int, float))
    xlsx_is_num = isinstance(xlsx_n, (int, float))

    # One empty, other has content
    if csv_n is None and xlsx_n is not None:
        if isinstance(xlsx_n, str):
            return 'пустое vs "нет"'
        return 'пустое vs число'
    if csv_n is not None and xlsx_n is None:
        if isinstance(csv_n, str):
            return '"нет" vs пустое'
        return 'число vs пустое'

    # Both numeric
    if csv_is_num and xlsx_is_num:
        if abs(csv_n - xlsx_n) < 0.5:
            return None  # effectively equal (rounding)
        diff = abs(csv_n - xlsx_n)
        avg = (abs(csv_n) + abs(xlsx_n)) / 2
        ratio = xlsx_n / csv_n if csv_n != 0 else None

        if csv_n != 0 and xlsx_n != 0 and abs(csv_n) == abs(xlsx_n):
            return 'знак'
        if ratio is not None and abs(abs(ratio) - 1000) < 0.01:
            return 'масштаб x1000'
        if ratio is not None and abs(abs(ratio) - 0.001) < 0.0001:
            return 'масштаб /1000'
        if avg > 0 and diff / avg < 0.05:
            return 'перестановка цифр / опечатка (<5%)'
        return 'значение заменено'

    # Mixed types
    if isinstance(csv_n, str) and isinstance(xlsx_n, str):
        return f'строка vs строка: "{csv_n}" vs "{xlsx_n}"'
    if isinstance(csv_n, str):
        return f'строка "{csv_n}" vs число {xlsx_n}'
    if isinstance(xlsx_n, str):
        return f'число {csv_n} vs строка "{xlsx_n}"'

    return 'прочее'


def trace_to_json(emitter, code, year):
    """Find the source JSON value for this cell. Returns (json_value, trace_string, pipeline_stage)."""
    year_int = int(year)

    # For balance: look in the emitter's own year file
    if FORM_OF.get(code) == 'bal':
        json_path = EXTRACTED / f'{emitter}_6мес_{year_int}.json'
        if not json_path.exists():
            return None, f'JSON не найден: {json_path.name}', 'нет JSON'

        try:
            d = json.load(open(json_path, encoding='utf-8'))
        except Exception as e:
            return None, f'Ошибка чтения: {e}', 'ошибка JSON'

        bal = d.get('balance')
        if not bal:
            return None, f'Нет balance в JSON', 'нет balance'

        svod.mark_chains(bal)
        bal_idx = svod.col_index_balance(bal, year_int)
        if bal_idx is None:
            return None, f'Баланс: колонка {year} не найдена (cols={bal.get("columns")})', 'колонка не найдена'

        # For 1450/1550 with rent, replicate pipeline logic
        if code in ('1450', '1550'):
            long_v, short_v, notes, susp = svod.rent_extract(bal, bal_idx)
            base = svod.get_val(bal, code, bal_idx)
            if code == '1450':
                if long_v is not None:
                    val = (base or 0) + long_v
                else:
                    val = base
            else:
                if short_v is not None:
                    val = (base or 0) + short_v
                else:
                    val = base
        else:
            val = svod.get_val(bal, code, bal_idx)

        return val, f'JSON bal [{json_path.name}] idx={bal_idx}', 'pipeline'

    # For OFR/ODDS: from 2026 file
    if code in svod.IS_CODES or code in svod.CF_CODES:
        json_path = EXTRACTED / f'{emitter}_6мес_2026.json'
        if not json_path.exists():
            return None, f'JSON 2026 не найден', 'нет JSON'

        try:
            d = json.load(open(json_path, encoding='utf-8'))
        except Exception as e:
            return None, f'Ошибка чтения: {e}', 'ошибка JSON'

        if code in svod.IS_CODES:
            form = d.get('income_statement')
            form_name = 'income_statement'
        else:
            form = d.get('cash_flow')
            form_name = 'cash_flow'

        if not form:
            return None, f'Нет {form_name} в JSON', f'нет {form_name}'

        svod.mark_chains(form)
        idx = svod.col_index_flow(form, year_int)
        if idx is None:
            return None, f'{form_name}: колонка {year} не найдена', 'колонка не найдена'

        val = svod.get_val(form, code, idx)
        if code == '2330' and val is not None:
            val = abs(val)
        return val, f'JSON {form_name} [{json_path.name}] idx={idx}', 'pipeline'

    return None, f'Неизвестный код {code}', 'код не известен'


def main():
    csv_data, csv_col_map = parse_csv()
    xlsx_data = parse_xlsx()

    # --- 1. Structural comparison ---
    csv_emitters = list(csv_data.keys())
    xlsx_emitters = [e for e in xlsx_data.keys()]
    csv_set = set(csv_emitters)
    xlsx_set = set(xlsx_emitters)

    added_in_xlsx = sorted(xlsx_set - csv_set)
    removed_from_xlsx = sorted(csv_set - xlsx_set)
    common = csv_set & xlsx_set

    print('=' * 80)
    print('STRUCTURAL COMPARISON')
    print('=' * 80)
    print(f'CSV emitters:  {len(csv_emitters)}')
    print(f'XLSX emitters: {len(xlsx_emitters)}')
    if added_in_xlsx:
        print(f'  Added in XLSX: {added_in_xlsx}')
    if removed_from_xlsx:
        print(f'  Removed from XLSX (in CSV only): {removed_from_xlsx}')
    print(f'Common: {len(common)}')

    # Column comparison
    csv_cols = set(tuple(c) for c in csv_col_map)  # set of (year, code)
    xlsx_cols = set()
    # Rebuild xlsx col set from the known structure
    for ci, code in enumerate(CODES):
        xlsx_cols.add(('2025', code))
        xlsx_cols.add(('2026', code))

    csv_only_cols = sorted(csv_cols - xlsx_cols)
    xlsx_only_cols = sorted(xlsx_cols - csv_cols)
    print(f'\nCSV columns:  {len(csv_cols)}')
    print(f'XLSX columns: {len(xlsx_cols)}')
    if csv_only_cols:
        print(f'  In CSV only: {csv_only_cols}')
    if xlsx_only_cols:
        print(f'  In XLSX only: {xlsx_only_cols}')

    # --- 2. Cell-by-cell comparison ---
    diffs = []
    for emitter in xlsx_emitters:
        if emitter not in csv_data:
            # Added row in XLSX
            xlsx_cells = xlsx_data[emitter]
            for (year, code), val in sorted(xlsx_cells.items()):
                if val is not None and val != '':
                    diffs.append({
                        'emitter': emitter, 'code': code, 'year': year,
                        'csv_val': '', 'xlsx_val': val,
                        'category': 'строка добавлена в XLSX',
                    })
            continue

        csv_cells = csv_data[emitter]
        xlsx_cells = xlsx_data[emitter]
        all_keys = set(csv_cells.keys()) | set(xlsx_cells.keys())
        for year, code in sorted(all_keys):
            csv_val = csv_cells.get((year, code), '')
            xlsx_val = xlsx_cells.get((year, code))

            csv_n = norm_num(csv_val)
            xlsx_n = norm_num(xlsx_val)

            # Both empty/None -> no diff
            if csv_n is None and xlsx_n is None:
                continue
            # Both numeric and close -> no diff
            if isinstance(csv_n, (int, float)) and isinstance(xlsx_n, (int, float)):
                if abs(csv_n - xlsx_n) < 0.5:
                    continue
            # Both 'нет' -> no diff
            if csv_n == xlsx_n:
                continue

            cat = classify_difference(csv_val, xlsx_val)
            if cat is None:
                continue

            diffs.append({
                'emitter': emitter, 'code': code, 'year': year,
                'csv_val': csv_val, 'xlsx_val': xlsx_val,
                'category': cat,
            })

    # --- 3. Trace each to JSON ---
    for d in diffs:
        json_val, trace, stage = trace_to_json(d['emitter'], d['code'], d['year'])
        d['json_val'] = json_val
        d['trace'] = trace
        d['stage'] = stage

        csv_n = norm_num(d['csv_val'])
        xlsx_n = norm_num(d['xlsx_val'])
        jn = norm_num(json_val) if json_val is not None else None

        # Determine who is right
        if stage != 'pipeline':
            d['verdict'] = stage  # cannot determine
        elif jn is None:
            if csv_n is None and isinstance(xlsx_n, (int, float)):
                d['verdict'] = 'XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source'
            elif csv_n == '\u043d\u0435\u0442' and xlsx_n is None:
                d['verdict'] = 'XLSX empty vs CSV "нет" -> consistent (no file for that year)'
            else:
                d['verdict'] = 'недостаточно данных в JSON для определения'
        elif isinstance(jn, (int, float)):
            if isinstance(csv_n, (int, float)) and abs(csv_n - jn) < 0.5:
                if isinstance(xlsx_n, (int, float)) and abs(xlsx_n - jn) >= 0.5:
                    d['verdict'] = 'CSV = JSON (pipeline OK); XLSX differs (human correction)'
                elif xlsx_n is None:
                    d['verdict'] = 'CSV = JSON; XLSX empty (human cleared the cell?)'
                else:
                    d['verdict'] = 'непонятно'
            elif isinstance(xlsx_n, (int, float)) and abs(xlsx_n - jn) < 0.5:
                if isinstance(csv_n, (int, float)):
                    d['verdict'] = 'XLSX = JSON (correct); CSV differs -> pipeline error in CSV'
                elif csv_n is None:
                    d['verdict'] = 'XLSX = JSON; CSV empty -> pipeline missed this value'
                else:
                    d['verdict'] = 'непонятно'
            elif isinstance(csv_n, (int, float)) and isinstance(xlsx_n, (int, float)):
                # Neither matches JSON exactly
                d['verdict'] = 'both CSV and XLSX differ from JSON -> complex'
            else:
                d['verdict'] = 'требует анализа'
        else:
            d['verdict'] = 'требует анализа'

    # --- 4. Report ---
    print()
    print('=' * 80)
    print(f'CELL DIFFERENCES: {len(diffs)}')
    print('=' * 80)

    # Category counts
    cats = {}
    for d in diffs:
        cats[d['category']] = cats.get(d['category'], 0) + 1
    print('\nDifference categories:')
    for cat, cnt in sorted(cats.items(), key=lambda x: -x[1]):
        print(f'  {cat}: {cnt}')

    # Verdict counts
    verdicts = {}
    for d in diffs:
        v = d['verdict']
        verdicts[v] = verdicts.get(v, 0) + 1
    print('\nVerdict counts:')
    for v, cnt in sorted(verdicts.items(), key=lambda x: -x[1]):
        print(f'  {v}: {cnt}')

    # Filter out the naming artifact: CSV "1450+аренда" vs XLSX "1450" are same columns
    # These appear as paired diffs: one "число vs пустое" and one "пустое vs число"
    # with matching values. Let's detect and annotate these.
    print()
    print('=' * 80)
    print('DETAILED DIFF LIST (first 80):')
    print('=' * 80)

    shown = 0
    for i, d in enumerate(diffs):
        if shown >= 80:
            remaining = len(diffs) - shown
            print(f'\n... and {remaining} more differences (see full list in stdout log)')
            break
        shown += 1

        csv_disp = repr(d['csv_val']) if d['csv_val'] else '(empty)'
        xlsx_disp = repr(d['xlsx_val']) if d['xlsx_val'] is not None else '(empty)'
        json_disp = repr(d['json_val']) if d['json_val'] is not None else '(none)'

        print(f'{i+1:3d}. {d["emitter"]:<25s} | {d["code"]:>5s}_{d["year"]:<5s} | CSV={csv_disp:<16s} | XLSX={xlsx_disp:<16s} | JSON={json_disp}')
        print(f'     Cat: {d["category"]}  | Stage: {d["stage"]}')
        print(f'     Trace: {d["trace"]}')
        print(f'     Verdict: {d["verdict"]}')
        print()

    # Summary of remaining
    if len(diffs) > 80:
        print(f'\n--- SUMMARY of remaining {len(diffs) - 80} diffs ---')
        remaining = diffs[80:]
        rem_cats = {}
        for d in remaining:
            rem_cats[d['category']] = rem_cats.get(d['category'], 0) + 1
        for cat, cnt in sorted(rem_cats.items(), key=lambda x: -x[1]):
            print(f'  {cat}: {cnt}')

    # Write markdown report
    md_path = EXTRACTED.parent / '_diff_gold.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('# Diff Report: svod_2025_2026.csv vs svod_2025_2026.xlsx\n\n')
        f.write(f'**CSV:** `{CSV_PATH}`\n')
        f.write(f'**XLSX:** `{XLSX_PATH}`\n')
        f.write(f'**Total differing cells:** {len(diffs)}\n\n')

        f.write('## Structure\n')
        f.write(f'- CSV emitters: {len(csv_emitters)}\n')
        f.write(f'- XLSX emitters: {len(xlsx_emitters)}\n')
        if added_in_xlsx:
            f.write(f'- Added in XLSX: {", ".join(added_in_xlsx)}\n')
        if removed_from_xlsx:
            f.write(f'- Removed from XLSX: {", ".join(removed_from_xlsx)}\n')
        f.write(f'- Columns: {len(csv_cols)} (identical sets)\n\n')

        f.write('## Category Counts\n')
        for cat, cnt in sorted(cats.items(), key=lambda x: -x[1]):
            f.write(f'- {cat}: {cnt}\n')
        f.write('\n')

        f.write('## Verdict Counts\n')
        for v, cnt in sorted(verdicts.items(), key=lambda x: -x[1]):
            f.write(f'- {v}: {cnt}\n')
        f.write('\n')

        f.write('## Full Diff List\n\n')
        f.write('| # | Emitter | Key | CSV | XLSX | JSON | Category | Stage | Verdict |\n')
        f.write('|---|---------|-----|-----|------|------|----------|-------|---------|\n')
        for i, d in enumerate(diffs):
            csv_disp = str(d['csv_val']) if d['csv_val'] else ''
            xlsx_disp = str(d['xlsx_val']) if d['xlsx_val'] is not None else ''
            json_disp = str(d['json_val']) if d['json_val'] is not None else ''
            f.write(f'| {i+1} | {d["emitter"]} | {d["code"]}_{d["year"]} | {csv_disp} | {xlsx_disp} | {json_disp} | {d["category"]} | {d["stage"]} | {d["verdict"]} |\n')

    print(f'\nMarkdown report written to: {md_path}')


if __name__ == '__main__':
    main()
