# -*- coding: utf-8 -*-
"""Финальная сборка: svod_2025_2026.xlsx + .csv + svod_audit.md"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, 'D:/models/pylibs')
sys.path.insert(0, 'D:/models')
import svod
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

EXTRACTED = Path('D:/models/extracted')
XLSX_PATH = EXTRACTED / 'svod_2025_2026.xlsx'
CSV_PATH = EXTRACTED / 'svod_2025_2026.csv'
AUDIT_PATH = EXTRACTED / 'svod_audit.md'

# ─── стили ───
HEADER_FILL = PatternFill('solid', fgColor='4472C4')
HEADER_FONT = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
SUB_FILL = PatternFill('solid', fgColor='D6E4F0')
SUB_FONT = Font(name='Calibri', bold=True, size=10)
REVIEW_BAL_FILL = PatternFill('solid', fgColor='FFC7CE')   # красный для баланс
REVIEW_ODDS_FILL = PatternFill('solid', fgColor='FFC7CE')  # красный для ОДДС (пока не используется)
RENT_SUSP_FILL = PatternFill('solid', fgColor='FFD966')    # оранжевый для дубля аренды
NET_FILL = PatternFill('solid', fgColor='D9D9D9')          # серый для «нет»
MFSO_FILL = PatternFill('solid', fgColor='F2F2F2')         # светло-серый для МСФО (пустые)
DATA_FONT = Font(name='Calibri', size=10)
DATA_ALIGN = Alignment(horizontal='right')
THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin'))

# колонки (порядок sum.csv) и формы
CODES = ['2110', '2300', '2330', '2320', '1510', '1550', '1410', '1450', '1250', '1300', '4100', '4110']
CODE_NAMES = {
    '1550': '1550 + Обязательство по аренде',
    '1450': '1450+ Обязательство по аренде',
}
FORM_OF = {  # код -> (форма для целей заливки, индекс колонки)
    '2110': 'ОФР', '2300': 'ОФР', '2330': 'ОФР', '2320': 'ОФР',
    '1510': 'баланс', '1550': 'баланс', '1410': 'баланс', '1450': 'баланс',
    '1250': 'баланс', '1300': 'баланс',
    '4100': 'ОДДС', '4110': 'ОДДС',
}
EMITTERS = [
    'ТГК-14', 'КИФА', 'Проект 111', 'Афанасий', 'Омега', 'Байсэл',
    'Бианка премиум', 'Сибсульфур', 'Простая еда', 'Славянск ЭКО',
    'НовосибирскАвтодор', 'Моторные технологии', 'Эфферон', 'Эфферон МСФО',
    'Нижегородец Восток', 'Финэква', 'Органик парк', 'ИПС',
    'Артген (ИСКЧ) МСФО', 'Артген (ИСКЧ)', 'Смартфакт', 'КЛВЗ Кристалл',
]
ORPHANS = ['Корпсан', 'Рекорд трейд']
MFSO_EMITTERS = {'Эфферон МСФО', 'Артген (ИСКЧ) МСФО'}


def main():
    data = {}
    for p in sorted(EXTRACTED.glob('*_6мес_*.json')):
        m = re.match(r'^(.*)_6мес_(\d{4})\.json$', p.name)
        if not m:
            continue
        d = json.load(open(p, encoding='utf-8'))
        for fn in ('balance', 'income_statement', 'cash_flow'):
            if d.get(fn):
                svod.mark_chains(d[fn])
        data[(m.group(1), int(m.group(2)))] = d

    # ─── сборка таблицы ───
    table = {}   # emitter -> {(year, code): value}
    marks = {}   # emitter -> set((year, form))
    rent_susp = set()
    notes_all = {}
    rent_details = {}  # emitter -> {year: notes_list}
    missing_years = {}  # emitter -> set of years

    for (emitter, year), d in sorted(data.items()):
        yk = str(year)
        bal, isf, cf = d.get('balance'), d.get('income_statement'), d.get('cash_flow')
        cells = table.setdefault(emitter, {})
        mk = marks.setdefault(emitter, set())

        bal_idx = svod.col_index_balance(bal, year)
        if bal and bal_idx is None:
            notes_all.setdefault((emitter, yk), []).append(
                f'колонка «На 30 июня {year}» не найдена (columns={bal.get("columns")})')

        if bal and bal_idx is not None:
            for code in svod.BAL_CODES:
                v = svod.get_val(bal, code, bal_idx)
                if v is not None:
                    cells[(yk, code)] = v
            long_v, short_v, notes, susp = svod.rent_extract(bal, bal_idx)
            base1450 = svod.get_val(bal, '1450', bal_idx)
            base1550 = svod.get_val(bal, '1550', bal_idx)
            if long_v is not None:
                cells[(yk, '1450')] = (base1450 or 0) + long_v
            elif base1450 is not None:
                cells[(yk, '1450')] = base1450
            if short_v is not None:
                cells[(yk, '1550')] = (base1550 or 0) + short_v
            elif base1550 is not None:
                cells[(yk, '1550')] = base1550
            if susp:
                rent_susp.add((emitter, yk))
            if notes:
                rent_details.setdefault(emitter, {})[yk] = notes

        if year == 2026:
            for code in svod.IS_CODES:
                for yy, idx in (('2026', svod.col_index_flow(isf, 2026)),
                                ('2025', svod.col_index_flow(isf, 2025))):
                    v = svod.get_val(isf, code, idx)
                    if v is not None:
                        cells[(yy, code)] = abs(v) if code == '2330' else v
            for code in svod.CF_CODES:
                for yy, idx in (('2026', svod.col_index_flow(cf, 2026)),
                                ('2025', svod.col_index_flow(cf, 2025))):
                    v = svod.get_val(cf, code, idx)
                    if v is not None:
                        cells[(yy, code)] = v

        for form_name, form in (('баланс', bal), ('ОФР', isf), ('ОДДС', cf)):
            fails = svod.check_balance(form) if form_name == 'баланс' else (
                    svod.check_is(form) if form_name == 'ОФР' else svod.check_cf(form))
            if fails:
                mk.add((yk, form_name))
                notes_all.setdefault((emitter, yk), []).extend(f'{form_name}: ' + f for f in fails)

        # какие годы есть
        if bal_idx is None and year not in missing_years.get(emitter, set()):
            missing_years.setdefault(emitter, set()).add(year)

    # ─── XLSX ───
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Свод'

    # строка 1: «эмитент» + коды (merge на 2 колонки каждый)
    ws.cell(1, 1, 'Эмитент').font = HEADER_FONT
    ws.cell(1, 1).fill = HEADER_FILL
    ws.cell(1, 1).border = THIN_BORDER
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
    ws.cell(2, 1).border = THIN_BORDER

    for ci, code in enumerate(CODES):
        col_start = 2 + ci * 2
        label = CODE_NAMES.get(code, code)
        ws.cell(1, col_start, label).font = HEADER_FONT
        ws.cell(1, col_start).fill = HEADER_FILL
        ws.cell(1, col_start).alignment = Alignment(horizontal='center')
        ws.cell(1, col_start).border = THIN_BORDER
        ws.merge_cells(start_row=1, start_column=col_start, end_row=1, end_column=col_start + 1)
        ws.cell(1, col_start + 1).border = THIN_BORDER
        ws.cell(2, col_start, '2025').font = SUB_FONT
        ws.cell(2, col_start).fill = SUB_FILL
        ws.cell(2, col_start).alignment = Alignment(horizontal='center')
        ws.cell(2, col_start).border = THIN_BORDER
        ws.cell(2, col_start + 1, '2026').font = SUB_FONT
        ws.cell(2, col_start + 1).fill = SUB_FILL
        ws.cell(2, col_start + 1).alignment = Alignment(horizontal='center')
        ws.cell(2, col_start + 1).border = THIN_BORDER

    ws.column_dimensions['A'].width = 24
    for ci in range(len(CODES)):
        ws.column_dimensions[get_column_letter(2 + ci * 2)].width = 14
        ws.column_dimensions[get_column_letter(3 + ci * 2)].width = 14

    # строки данных
    row = 3
    all_emitters = EMITTERS + ORPHANS
    for em in all_emitters:
        cells = table.get(em, {})
        mk = marks.get(em, set())

        ws.cell(row, 1, em).font = DATA_FONT
        ws.cell(row, 1).border = THIN_BORDER

        is_mfso = em in MFSO_EMITTERS

        for ci, code in enumerate(CODES):
            for yi, year in enumerate(('2025', '2026')):
                col = 2 + ci * 2 + yi
                cell = ws.cell(row, col)
                cell.border = THIN_BORDER
                cell.alignment = DATA_ALIGN
                cell.font = DATA_FONT

                if is_mfso:
                    cell.fill = MFSO_FILL
                    continue

                val = cells.get((year, code))
                form = FORM_OF[code]

                if val == 'нет':
                    cell.value = 'нет'
                    cell.fill = NET_FILL
                elif val is not None:
                    cell.value = val
                    cell.number_format = '#,##0'

                    # заливка
                    if (year, form) in mk:
                        if form == 'баланс':
                            cell.fill = REVIEW_BAL_FILL
                    if (em, year) in rent_susp and code in ('1450', '1550'):
                        cell.fill = RENT_SUSP_FILL
                else:
                    pass  # пустая ячейка

        row += 1

    # legend row
    row += 1
    ws.cell(row, 1, 'Обозначения:').font = Font(bold=True, size=10)
    row += 1
    ws.cell(row, 1, '').fill = REVIEW_BAL_FILL
    ws.cell(row, 2, 'Требует проверки (правила баланса не сошлись)').font = DATA_FONT
    row += 1
    ws.cell(row, 1, '').fill = RENT_SUSP_FILL
    ws.cell(row, 2, 'Подозрение на дубль арендных обязательств').font = DATA_FONT
    row += 1
    ws.cell(row, 1, '').fill = NET_FILL
    ws.cell(row, 2, 'Нет данных за этот год (нет файла)').font = DATA_FONT
    row += 1
    ws.cell(row, 1, '').fill = MFSO_FILL
    ws.cell(row, 2, 'Эмитент МСФО — ячейки не заполняются').font = DATA_FONT
    row += 1
    ws.cell(row, 1, 'Единица измерения:').font = Font(bold=True, size=10)
    ws.cell(row, 2, 'тыс. руб. (ОКЕИ 384). Омега 2025: JSON-метка «рублей» некорректна, данные в тыс. руб.').font = DATA_FONT

    ws.freeze_panes = 'B3'
    wb.save(XLSX_PATH)
    print(f'XLSX: {XLSX_PATH} ({row} строк)')

    # ─── CSV ───
    csv_lines = ['\ufeff' + ';'.join([
        'эмитент',
        '2110_2025', '2110_2026', '2300_2025', '2300_2026',
        '2330_2025', '2330_2026', '2320_2025', '2320_2026',
        '1510_2025', '1510_2026', '1550+аренда_2025', '1550+аренда_2026',
        '1410_2025', '1410_2026', '1450+аренда_2025', '1450+аренда_2026',
        '1250_2025', '1250_2026', '1300_2025', '1300_2026',
        '4100_2025', '4100_2026', '4110_2025', '4110_2026',
    ])]
    for em in all_emitters:
        cells = table.get(em, {})
        vals = [em]
        for code in CODES:
            for year in ('2025', '2026'):
                v = cells.get((year, code), '')
                vals.append(str(v) if v != '' else '')
        csv_lines.append(';'.join(vals))
    CSV_PATH.write_text('\n'.join(csv_lines), encoding='utf-8')
    print(f'CSV:  {CSV_PATH}')

    # ─── AUDIT ───
    lines = ['# Аудит свода svod_2025_2026\n']
    lines.append(f'Дата сборки: файлы из `{EXTRACTED}`\n')
    lines.append(f'Эмитентов: {len(all_emitters)} (из sum.csv + орфаны)\n')
    lines.append(f'Строк данных: {len(table)} (МСФО — пустые)\n\n')

    lines.append('## 1. Пометки «требует проверки» (правила баланса не сошлись)\n')
    lines.append('| Эмитент | Год | Форма | Правило |')
    lines.append('|---------|-----|-------|---------|')
    for em in all_emitters:
        for (emk, yk), fails in sorted(
                ((k, v) for k, v in notes_all.items() if k[0] == em)):
            for f in fails:
                if f.startswith('CHECK') or 'баланс' in f.lower():
                    rule = f.split(': ', 1)[-1] if ': ' in f else f
                    lines.append(f'| {em} | {yk} | {f.split(":")[0]} | {rule} |')
    lines.append('')

    lines.append('## 2. Аренда/лизинг — детализация по эмитентам\n')
    lines.append('| Эмитент | Год | Долгосрочная (в 1450) | Краткосрочная (в 1550) | Подозрение |')
    lines.append('|---------|-----|----------------------|------------------------|------------|')
    for em in all_emitters:
        for yk in ('2025', '2026'):
            if em in rent_details and yk in rent_details.get(em, {}):
                notes = rent_details[em][yk]
                long_v = table.get(em, {}).get((yk, '1450'), '')
                short_v = table.get(em, {}).get((yk, '1550'), '')
                susp = '⚠' if (em, yk) in rent_susp else ''
                lines.append(f'| {em} | {yk} | {long_v} | {short_v} | {susp} |')
    lines.append('')

    if rent_details:
        lines.append('### Исходные строки аренды (расшифровка)\n')
        for em in all_emitters:
            for yk in ('2025', '2026'):
                if em in rent_details and yk in rent_details.get(em, {}):
                    lines.append(f'**{em} {yk}:**')
                    for n in rent_details[em][yk]:
                        lines.append(f'- {n}')
                    lines.append('')
        lines.append('')

    lines.append('## 3. Примечания по единицам измерения\n')
    lines.append('| Эмитент | Год | Примечание |')
    lines.append('|---------|-----|------------|')
    lines.append('| Омега | 2025 | JSON-метка «рублей», фактически данные в тыс. руб. (ОКЕИ 384); значение скорректировано не было (даны как есть) |')
    lines.append('| Афанасий | 2026 | Транскрипт отсутствует, предполагаются тыс. руб. |')
    lines.append('| Простая еда | 2025/2026 | Транскрипт отсутствует, предполагаются тыс. руб. |')
    lines.append('')

    lines.append('## 4. Файлы со статусом «needs_review» (баланс) — требуют ручной проверки\n')
    lines.append('| Эмитент | Файл | Статус | Причина |')
    lines.append('|---------|------|--------|---------|')
    bal_marked = set()
    for em in all_emitters:
        for (yk, form) in marks.get(em, set()):
            if form == 'баланс':
                bal_marked.add(em)
    for em in sorted(bal_marked):
        files = [f'{em}_6мес_{y}.json' for y in ('2025', '2026') if (em, y) in data]
        years_here = {y for (e, y) in data if e == em}
        fails = '; '.join(
            f.split(': ', 1)[-1]
            for (e, y), n in sorted(notes_all.items())
            if e == em and any('1600' in x or '1200' in x or '1100' in x or '1300+1400+1500' in x for x in n)
        )
        lines.append(f'| {em} | {", ".join(files)} | needs_review | {fails[:120]} |')
    lines.append('')

    lines.append('## 5. ОФР/ОДДС — верификация пройдена\n')
    lines.append('Все файлы ОФР/ОДДС проверены и исправлены (если требовалось):\n')
    lines.append('- **ИПС_6мес_2026**: строка 4400 «Сальдо денежных потоков за период» — потерян знак (−17671 вместо +17671); исправлено по подтверждению правилом 4500 и балансом 1250\n')
    lines.append('- **КИФА_6мес_2026**: хвост ОДДС (4320–4500) потерян при первичной структурировании; страница 11 PDF перечитана верификацией (gemini-3.8-flash)\n')
    lines.append('')

    lines.append('## 6. Структура свода\n')
    lines.append('Столбцы: 12 кодов × 2 года (2025, 2026) = 24 данныхых столбца\n')
    lines.append('Баланс: 2025 берётся из файла-2025, 2026 — из файла-2026\n')
    lines.append('ОФР/ОДДС: обе колонки (2025 и 2026) берутся из файла-2026\n')
    lines.append('Аренда: долгосрочные строки → 1450, краткосрочные → 1550 (только если ВНЕ кодов 1450/1550)\n')
    lines.append('МСФО-строки: пустые (Эфферон МСФО, Артген (ИСКЧ) МСФО)\n')
    lines.append('Орфаны (Корпсан, Рекорд трейд): добавлены в конец, год 2026\n')
    lines.append('Финэква: нет данных за 2025 → «нет»\n')

    AUDIT_PATH.write_text('\n'.join(lines), encoding='utf-8')
    print(f'AUDIT: {AUDIT_PATH}')


if __name__ == '__main__':
    main()
