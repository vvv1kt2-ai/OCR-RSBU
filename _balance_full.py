# -*- coding: utf-8 -*-
r"""Полный баланс по эмитентам, у которых не сошёлся баланс: ЕнисейАгроСоюз и Денум.

Зачем: свод берёт из баланса 12 строк, а невязка может сидеть в любой другой. Здесь
выгружается ВЕСЬ баланс, как он прочитан из файла, — все строки, все три колонки,
плюс построчная сверка итогов по каждой колонке отдельно, с разницей в рублях.
Это даёт ответ на вопрос «ошибка в отчёте или в чтении»: если слагаемые сходятся
с итогом, а итог раздела — нет, то ошибка в отчёте.

Выход: extracted/balance_full_ЕнисейАгроСоюз_Денум.xlsx
       extracted/balance_full_анализ.md

Запуск: python D:\models\_balance_full.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, r'D:\models\pylibs')
sys.path.insert(0, r'D:\models')
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
import svod as svod_mod

EXTRACTED = Path(r'D:\models\extracted')
OUT_XLSX = EXTRACTED / 'balance_full_ЕнисейАгроСоюз_Денум.xlsx'
OUT_MD = EXTRACTED / 'balance_full_анализ.md'

DOCS = [
    ('ЕнисейАгроСоюз', 2026),
    ('ЕнисейАгроСоюз', 2025),
    ('Денум', 2026),
    ('Денум', 2025),
]

# Итоги и то, из чего они обязаны складываться.
RULES = [
    ('1100', 'Итого по разделу I', ['1110', '1120', '1130', '1140', '1150', '1160',
                                    '1170', '1180', '1190']),
    ('1200', 'Итого по разделу II', ['1210', '1215', '1220', '1230', '1240', '1250', '1260']),
    ('1600', 'БАЛАНС (актив)', ['1100', '1200']),
    ('1300', 'Итого по разделу III', ['1310', '1320', '1340', '1350', '1360', '1370']),
    ('1400', 'Итого по разделу IV', ['1410', '1420', '1430', '1440', '1450']),
    ('1500', 'Итого по разделу V', ['1510', '1520', '1530', '1540', '1550']),
    ('1700', 'БАЛАНС (пассив)', ['1300', '1400', '1500']),
    ('1600', 'АКТИВ = ПАССИВ', ['1700']),
]

BOLD = Font(bold=True)
TITLE = Font(bold=True, size=12)
HEAD = Font(bold=True, color='FFFFFF')
HEAD_FILL = PatternFill('solid', fgColor='44546A')
BAD_FILL = PatternFill('solid', fgColor='FFC7CE')
WARN_FILL = PatternFill('solid', fgColor='FFEB9C')
GOOD_FILL = PatternFill('solid', fgColor='C6EFCE')
NOTE = PatternFill('solid', fgColor='FFF2CC')

# Допуск тот же, что у конвейера (svod.TOL): расхождение в 1–2 тыс. руб. — это округление
# внутри отчёта, и правила его пропускают. Показываем такие отдельно от настоящих невязок,
# иначе ±1 в каждой колонке заслоняет то, ради чего таблица построена.
TOL = 2


def load(em, year):
    p = EXTRACTED / f'{em}_6мес_{year}.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None


def tops(bal):
    """Верхние строки: код -> значения. Только верхний уровень (как в отчёте)."""
    out = {}
    for it in bal.get('items') or []:
        c = it.get('code')
        if c:
            out.setdefault(c, it)
    return out


def val(d, code, c):
    it = d.get(code)
    if not it:
        return None
    v = it.get('values') or []
    return v[c] if c < len(v) else None


def fmt(x):
    if x is None:
        return '—'
    if isinstance(x, str):
        return x
    return f'{x:,}'.replace(',', ' ')


wb = openpyxl.Workbook()
wb.remove(wb.active)
md = ['# Полный баланс: где не сходится', '',
      'Выгружен весь баланс, как он прочитан из файлов, и построчная сверка итогов '
      'по каждой колонке отдельно. Разница показана в тех же единицах, что и отчёт '
      '(тыс. руб., ОКЕИ 384).', '',
      f'Допуск ±{TOL} тыс. руб. — как у конвейера: такие расхождения он пропускает как '
      'округление внутри отчёта. Ниже сначала идут невязки ВНЕ допуска (это и есть ответ '
      'на вопрос «ошибка в отчёте или в чтении»), затем полные таблицы.', '']
# (эмитент, год, итог, колонка, значение итога, сумма слагаемых, разница)
findings = []

for em, year in DOCS:
    d = load(em, year)
    if d is None:
        continue
    bal = d.get('balance') or {}
    cols = list(bal.get('columns') or [])
    T = tops(bal)
    ws = wb.create_sheet(f'{em} {year}'[:31])

    ws['A1'] = f'{em} — бухгалтерский баланс, 6 мес. {year}'
    ws['A1'].font = TITLE
    ws['A2'] = f'файл: {em}_6мес_{year}.pdf     статус чтения: {d.get("status")}'
    ws['A3'] = ('единица: ' + str(((d.get('unit') or {}).get('label')) or '—')
                + '     строк в артефакте: ' + str(len(bal.get('items') or [])))
    # Заголовок: «Код» + «Наименование» + все колонки отчёта. Цикл идёт по длине ЭТОГО
    # списка, а не по постоянному числу: у баланса три колонки, и жёсткое range(4) писало
    # только первые две — заголовок третьей оставался пустым (в данных она была).
    head = ['Код', 'Наименование', *cols]
    for c in range(len(head)):
        ws.cell(4, 1 + c).value = head[c]
    for c in range(1, 3 + len(cols)):
        cell = ws.cell(4, c)
        cell.font = HEAD
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(horizontal='center', wrap_text=True)

    r = 5
    for it in bal.get('items') or []:
        code = it.get('code') or ''
        name = it.get('name') or ''
        ws.cell(r, 1, code)
        ws.cell(r, 2, name)
        for c in range(len(cols)):
            v = (it.get('values') or [])
            x = v[c] if c < len(v) else None
            cell = ws.cell(r, 3 + c, x if not isinstance(x, str) else x)
            cell.number_format = '# ##0'
            cell.alignment = Alignment(horizontal='right')
        if code and code in {x[0] for x in RULES}:
            for c in range(1, 3 + len(cols)):
                ws.cell(r, c).font = BOLD
        r += 1
        for ch in it.get('children') or []:
            ws.cell(r, 1, ch.get('code') or '')
            ws.cell(r, 2, '    ' + (ch.get('name') or ''))
            for c in range(len(cols)):
                v = (ch.get('values') or [])
                x = v[c] if c < len(v) else None
                cell = ws.cell(r, 3 + c, x if not isinstance(x, str) else x)
                cell.number_format = '# ##0'
                cell.alignment = Alignment(horizontal='right')
            r += 1

    # ─── сверка по колонкам ───
    r += 2
    ws.cell(r, 1, 'Сверка итогов по каждой колонке').font = TITLE
    r += 1
    ws.cell(r, 1, 'Итог')
    ws.cell(r, 2, 'Из чего складывается')
    for c in range(len(cols)):
        ws.cell(r, 3 + c, cols[c])
        ws.cell(r, 3 + c).font = HEAD
        ws.cell(r, 3 + c).fill = HEAD_FILL
    r += 1
    md.append(f'## {em} {year}')
    md.append('')
    md.append('| Итог | Из чего складывается | ' + ' | '.join(cols) + ' |')
    md.append('|------|----------------------|' + '---|' * len(cols))

    for code, label, parts in RULES:
        total = [val(T, code, c) for c in range(len(cols))]
        comp = []
        for c in range(len(cols)):
            s = None
            for p in parts:
                x = val(T, p, c)
                if x is not None:
                    s = (s or 0) + x
            comp.append(s)
        ws.cell(r, 1, f'{code} {label}')
        ws.cell(r, 2, '+'.join(parts))
        md_cells = []
        for c in range(len(cols)):
            diff = None
            if total[c] is not None and comp[c] is not None:
                diff = total[c] - comp[c]
            cell = ws.cell(r, 3 + c, total[c])
            cell.number_format = '# ##0'
            cell.alignment = Alignment(horizontal='right')
            if diff is not None and diff != 0:
                within = abs(diff) <= TOL
                cell.fill = WARN_FILL if within else BAD_FILL
                cell.value = (f'{fmt(total[c])}  (≠{fmt(comp[c])}, разница {fmt(diff)}'
                              + (', в допуске)' if within else ')'))
                tail = ' (в допуске)' if within else ''
                md_cells.append(f'**{fmt(total[c])}** ≠ {fmt(comp[c])} → '
                                f'**{fmt(diff)}**{tail}')
                if not within:
                    findings.append((em, year, f'{code} {label}', cols[c], total[c], comp[c], diff))
            else:
                md_cells.append(fmt(total[c]) if total[c] is not None else '—')
        md.append(f'| {code} {label} | {"+".join(parts)} | ' + ' | '.join(md_cells) + ' |')
        r += 1
    md.append('')

    # ─── разбор непрочитанных слагаемых ───
    gaps = []
    for code, label, parts in RULES:
        for c in range(len(cols)):
            total = val(T, code, c)
            have = [p for p in parts if val(T, p, c) is not None]
            miss = [p for p in parts if val(T, p, c) is None]
            if total is None or not miss:
                continue
            s = sum(val(T, p, c) for p in have)
            gaps.append((code, label, c, cols[c], total, s, total - s, miss))
    if gaps:
        r += 1
        ws.cell(r, 1, 'Незакрытые невязки: итог минус сумма прочитанных слагаемых').font = TITLE
        r += 1
        ws.cell(r, 1, 'Итог')
        ws.cell(r, 2, 'Колонка')
        ws.cell(r, 3, 'Значение итога')
        ws.cell(r, 4, 'Сумма прочитанных')
        ws.cell(r, 5, 'Разница')
        ws.cell(r, 6, 'Не прочитаны / напечатаны прочерком')
        for c in range(1, 7):
            ws.cell(r, c).font = HEAD
            ws.cell(r, c).fill = HEAD_FILL
        r += 1
        md.append('### Незакрытые невязки (итог минус сумма прочитанных слагаемых)')
        md.append('')
        md.append('| Итог | Колонка | Значение итога | Сумма прочитанных | Разница | '
                  'Слагаемые без значения |')
        md.append('|------|---------|----------------|-------------------|---------|'
                  '-----------------------|')
        for code, label, c, colname, total, s, diff, miss in gaps:
            ws.cell(r, 1, f'{code} {label}')
            ws.cell(r, 2, colname)
            ws.cell(r, 3, total).number_format = '# ##0'
            ws.cell(r, 4, s).number_format = '# ##0'
            cell = ws.cell(r, 5, diff)
            cell.number_format = '# ##0'
            cell.fill = BAD_FILL
            ws.cell(r, 6, ', '.join(miss))
            for cc in (3, 4, 5):
                ws.cell(r, cc).alignment = Alignment(horizontal='right')
            md.append(f'| {code} {label} | {colname} | {fmt(total)} | {fmt(s)} | '
                      f'**{fmt(diff)}** | {", ".join(miss)} |')
            r += 1
        md.append('')

    # ─── проверки самого артефакта ───
    chk = [c for c in (d.get('checks') or []) if c.get('form') == 'balance']
    if chk:
        r += 1
        ws.cell(r, 1, 'Проверки баланса, как их считает конвейер').font = TITLE
        r += 1
        ws.cell(r, 1, 'Правило')
        for c in range(len(cols)):
            ws.cell(r, 2 + c, cols[c])
            ws.cell(r, 2 + c).font = HEAD
            ws.cell(r, 2 + c).fill = HEAD_FILL
        r += 1
        md.append('### Проверки баланса')
        md.append('')
        md.append('| Правило | ' + ' | '.join(cols) + ' |')
        md.append('|---------|' + '---|' * len(cols))
        for c in chk:
            ws.cell(r, 1, c.get('rule'))
            per = c.get('per_column') or []
            cells = []
            for i in range(len(cols)):
                ok = per[i] if i < len(per) else None
                txt = '✓' if ok else ('✗' if ok is False else '—')
                cell = ws.cell(r, 2 + i, txt)
                cell.alignment = Alignment(horizontal='center')
                cell.fill = GOOD_FILL if ok else (BAD_FILL if ok is False else NOTE)
                cells.append(txt)
            md.append(f'| {c.get("rule")} | ' + ' | '.join(cells) + ' |')
            r += 1
        md.append('')

    for c in range(1, 7):
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 26
    ws.column_dimensions['B'].width = 52
    ws.freeze_panes = 'C5'

# ─── аренда: отдельная находка по этим же эмитентам ───
# Это НЕ про баланс. Строка аренды без кода не входит ни в один итог, поэтому баланс от неё
# не страдает. Но свод берёт в колонку «1550 + аренда» напечатанный код 1550 плюс
# обязательства по аренде, найденные ВНЕ кодов 1450/1550, — значит дубль такой строки
# искажает свод. Здесь видно, сколько строк аренды найдено и сколько из них признано копиями.
lease_rows = []
for em, year in DOCS:
    d = load(em, year)
    if d is None or not d.get('balance'):
        continue
    bal = d['balance']
    svod_mod.mark_chains(bal)
    cols = list(bal.get('columns') or [])
    if not cols:
        continue
    long_v, short_v, notes, susp = svod_mod.rent_extract(bal, 0)
    base1550 = val(tops(bal), '1550', 0)
    dups = [n for n in notes if 'поглощённая копия' in n]
    lease_rows.append((em, year, cols[0], base1550, long_v, short_v, susp, dups, notes))

md.append('## Отдельно: строка аренды (это про свод, а не про баланс)')
md.append('')
md.append('Строка аренды без кода не входит ни в один итог, поэтому баланс от неё не '
          'страдает. Но свод берёт в колонку «1550 + аренда» напечатанный код 1550 ПЛЮС '
          'обязательства по аренде, найденные вне кодов 1450/1550. Дубль такой строки '
          'в артефакте поэтому виден именно в своде.')
md.append('')
md.append('| Эмитент | Год | Колонка | 1550 в отчёте | Аренда найдена | Отброшено копий | '
          'Итог свода |')
md.append('|---------|-----|---------|---------------|----------------|-----------------|'
          '-----------|')
for em, year, colname, base1550, long_v, short_v, susp, dups, notes in lease_rows:
    total = (base1550 or 0) + (short_v or 0)
    md.append(f'| {em} | {year} | {colname} | {fmt(base1550)} | {fmt(short_v)} | '
              f'{len(dups)} | **{fmt(total)}** |')
md.append('')
for em, year, colname, base1550, long_v, short_v, susp, dups, notes in lease_rows:
    if not notes:
        continue
    md.append(f'**{em} {year}, {colname}** — что нашла разборка аренды:')
    md.append('')
    for n in notes:
        md.append(f'- {n}')
    md.append('')

# ─── лист «Главное» — первым ───
ws0 = wb.create_sheet('Главное')
ws0['A1'] = 'Где не сходится (невязки вне допуска)'
ws0['A1'].font = TITLE
ws0['A2'] = (f'Допуск ±{TOL} тыс. руб. — как у конвейера. Расхождения в его пределах '
             f'здесь не перечислены: это округление внутри отчёта.')
ws0['A3'] = ('Значения читаются из файлов как есть; невязка ниже означает, что напечатанный '
             'итог не равен сумме напечатанных слагаемых.')
hdr = ['Эмитент', 'Год', 'Итог', 'Колонка', 'В отчёте', 'Сумма слагаемых', 'Разница']
for i, h in enumerate(hdr, 1):
    c = ws0.cell(5, i, h)
    c.font = HEAD
    c.fill = HEAD_FILL
r0 = 6
for em, year, what, col, total, comp, diff in findings:
    ws0.cell(r0, 1, em)
    ws0.cell(r0, 2, year)
    ws0.cell(r0, 3, what)
    ws0.cell(r0, 4, col)
    for i, x in ((5, total), (6, comp), (7, diff)):
        cc = ws0.cell(r0, i, x)
        cc.number_format = '# ##0'
        cc.alignment = Alignment(horizontal='right')
    ws0.cell(r0, 7).fill = BAD_FILL
    r0 += 1
for i, w in enumerate((16, 8, 34, 24, 14, 17, 12), 1):
    ws0.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

# ─── лист «Аренда»: то же, что в разделе md, но листом ───
wsL = wb.create_sheet('Аренда')
wsL['A1'] = 'Аренда: сколько строк найдено и сколько признано копиями'
wsL['A1'].font = TITLE
wsL['A2'] = ('Строка аренды без кода не входит в итоги баланса, поэтому баланс от дубля не '
             'страдает. Свод же складывает 1550 отчёта с арендой, найденной вне кодов '
             '1450/1550, — там дубль и виден.')
lhdr = ['Эмитент', 'Год', 'Колонка', '1550 в отчёте', 'Аренда найдена',
        'Отброшено копий', 'Итог свода']
for i, h in enumerate(lhdr, 1):
    c = wsL.cell(4, i, h)
    c.font = HEAD
    c.fill = HEAD_FILL
    c.alignment = Alignment(horizontal='center', wrap_text=True)
rl = 5
for em, year, colname, base1550, long_v, short_v, susp, dups, notes in lease_rows:
    wsL.cell(rl, 1, em)
    wsL.cell(rl, 2, year)
    wsL.cell(rl, 3, colname)
    for i, x in ((4, base1550), (5, short_v), (6, len(dups)),
                 (7, (base1550 or 0) + (short_v or 0))):
        cc = wsL.cell(rl, i, x)
        cc.number_format = '# ##0'
        cc.alignment = Alignment(horizontal='right')
    if dups:
        wsL.cell(rl, 6).fill = BAD_FILL
    rl += 1
    for n in notes:
        wsL.cell(rl, 3, n)
        wsL.cell(rl, 3).font = Font(italic=True, size=9)
        rl += 1
for i, w in enumerate((16, 8, 26, 16, 16, 16, 16), 1):
    wsL.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

# Лист «Главное» — первым. Сдвиг считается от ТЕКУЩЕЙ позиции листа, а не от числа листов:
# offset = -(len(sheetnames) - 1) при шести листах давал -5 и позицию -1, а insert(-1, …)
# вставляет ПРЕД последним — лист оставался на пятом месте (замер: «Главное» оказалось
# после листов эмитентов). Поэтому берём индекс листа и сдвигаем ровно на него.
wb.move_sheet('Главное', offset=-wb.sheetnames.index('Главное'))
wb.save(OUT_XLSX)

# ─── сводка: только невязки вне допуска ───
if findings:
    # Блок собирается ЦЕЛИКОМ и вставляется одним куском. Поштучные insert(8, ...) в цикле
    # переворачивали порядок и разрывали таблицу: закрывающая фраза попадала между строками
    # невязок (замер: «Денум» оказался выше фразы, «ЕнисейАгроСоюз» — ниже).
    block = ['| Эмитент | Год | Итог | Колонка | В отчёте | Сумма слагаемых | Разница |',
             '|---------|-----|------|---------|----------|-----------------|---------|']
    for em, year, what, col, total, comp, diff in findings:
        block.append(f'| {em} | {year} | {what} | {col} | {fmt(total)} | {fmt(comp)} | '
                     f'**{fmt(diff)}** |')
    block.append('')
    block.append('**Всё остальное сходится в пределах ±%d (округление внутри отчёта).**' % TOL)
    block.append('')
    md[6:6] = block

OUT_MD.write_text('\n'.join(md) + '\n', encoding='utf-8')
print('XLSX:', OUT_XLSX)
print('MD:  ', OUT_MD)
print()
print('Невязки вне допуска ±%d:' % TOL)
for em, year, what, col, total, comp, diff in findings:
    print(f'  {em} {year}: {what} | {col} | в отчёте {fmt(total)}, '
          f'сумма слагаемых {fmt(comp)}, разница {fmt(diff)}')
if not findings:
    print('  нет')
