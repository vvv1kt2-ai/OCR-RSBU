# -*- coding: utf-8 -*-
"""Сборка свода ВДО за 9 месяцев 2025–2026 в xlsx.

Источник данных — D:\\models\\_свод_9мес.json (собран _свод_9мес.py из артефактов
извлечения). Здесь только оформление: две строки шапки, фиксация столбцов, фильтр,
числовой формат и разделитель ФАКУЛЬТАТИВ.
"""
import json, os, re

try:
    import openpyxl
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "openpyxl>=3.1.0"])
    import openpyxl

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def xl_color(css_hex: str) -> str:
    value = css_hex.removeprefix("#").upper()
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB, got: {css_hex}")
    return "FF" + value


XL_HEADER = xl_color("#4472C4")
XL_LIGHT = xl_color("#D9E2F3")
XL_BORDER = xl_color("#BFBFBF")
XL_SEP = xl_color("#EDEDED")
XL_DASH = xl_color("#FFF2CC")   # 0 вместо прочерка
XL_REVIEW = xl_color("#FDECEA")  # строка needs_review
XL_RISK = xl_color("#F8CBAD")    # значение, не сошедшееся по правилу

thin = Side(style="thin", color=XL_BORDER)
HEAD_FONT = Font(bold=True, color="FFFFFFFF", size=10)
HEAD_FILL = PatternFill("solid", fgColor=XL_HEADER)
SUB_FILL = PatternFill("solid", fgColor=XL_LIGHT)
SEP_FILL = PatternFill("solid", fgColor=XL_SEP)
DASH_FILL = PatternFill("solid", fgColor=XL_DASH)
REVIEW_FILL = PatternFill("solid", fgColor=XL_REVIEW)
RISK_FILL = PatternFill("solid", fgColor=XL_RISK)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center")

SRC = r"D:\models\_свод_9мес.json"
OUT = r"D:\models\Свод_ВДО_9мес_2025-2026.xlsx"

data = json.load(open(SRC, encoding="utf-8"))
h1, h2, rows, quality = data["header1"], data["header2"], data["rows"], data["quality"]

wb = openpyxl.Workbook()

# ─────────────── лист «Свод» ───────────────
ws = wb.active
ws.title = "Свод"
ws.sheet_properties.tabColor = XL_HEADER

NCOL = len(h1)
HEAD_ROW, SUB_ROW, FIRST = 1, 2, 3

for j, (a, b) in enumerate(zip(h1, h2), start=1):
    c1 = ws.cell(row=HEAD_ROW, column=j, value=a)
    c2 = ws.cell(row=SUB_ROW, column=j, value=b)
    c1.font, c1.fill, c1.alignment = HEAD_FONT, HEAD_FILL, CENTER
    c2.font, c2.fill, c2.alignment = Font(bold=True, size=9), SUB_FILL, CENTER
    c1.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    c2.border = Border(left=thin, right=thin, top=thin, bottom=thin)

STATUS_COL = (h1.index("Статус 2026") + 1) if "Статус 2026" in h1 else None

# какие клетки были прочерками: quality[i][6] = '2110_2025;4100_2026;...'
DASH_CELLS = []
RISK_CELLS = []
for q in quality:
    DASH_CELLS.append({x for x in (q[6].split(';') if len(q) > 6 and q[6] else []) if x})
    RISK_CELLS.append({x for x in (q[7].split(';') if len(q) > 7 and q[7] else []) if x})
# столбцы показателей: (код, год) -> индекс
METRIC_COL = {}
for j, h in enumerate(h1, start=1):
    if j <= 2:
        continue
    m = re.search(r'\((\d{4})\)', h)
    if m:
        METRIC_COL.setdefault(m.group(1), []).append(j)

r = FIRST
for i, row in enumerate(rows):
    is_sep = (len(row) > 1 and row[1] == "ФАКУЛЬТАТИВ")
    # Статус ищем по имени: после добавления столбцов со ссылками «последний столбец»
    # перестал быть статусом, и подсветка needs_review молча исчезла.
    status = row[STATUS_COL - 1] if STATUS_COL and len(row) >= STATUS_COL else ''
    review = (status == "needs_review" or status == "no_forms")
    dashes = DASH_CELLS[i] if i < len(DASH_CELLS) else set()
    risk = RISK_CELLS[i] if i < len(RISK_CELLS) else set()
    for j, v in enumerate(row, start=1):
        cell = ws.cell(row=r, column=j)
        if v == "" or v is None:
            cell.value = None
        else:
            cell.value = v
        # столбцы со ссылками: адрес остаётся текстом (его можно скопировать),
        # но клетка кликабельна
        if j > 2 and h1[j - 1] in ("Отчёт 2026", "Отчёт 2025") and isinstance(v, str) and v.startswith("http"):
            cell.hyperlink = v
            cell.font = Font(color="FF0563C1", underline="single", size=9)
            cell.alignment = Alignment(horizontal="left", vertical="center")
            continue
        if j <= 2:
            cell.alignment = LEFT
        else:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            if isinstance(v, (int, float)):
                cell.number_format = "#,##0"
        if is_sep:
            cell.fill = SEP_FILL
            cell.font = Font(bold=True, italic=True)
            continue
        if review:
            cell.fill = REVIEW_FILL
        # прочерк -> 0: подсвечиваем именно эти клетки, чтобы ноль не читался как факт
        code = h1[j - 1]
        m = re.search(r'\((\d{4})\)', code) if j > 2 else None
        if m:
            year = 2026 if h2[j - 1].endswith("2026") else 2025
            if f"{m.group(1)}_{year}" in dashes:
                cell.fill = DASH_FILL
            # значение, у которого не сошлось правило формы: подсвечиваем отдельно,
            # чтобы в строке needs_review было видно, ЧТО именно проверять
            if f"{m.group(1)}_{year}" in risk:
                cell.fill = RISK_FILL
                cell.font = Font(bold=True, color="FF9C0006")
    # статус: красным, чтобы 19 строк находились глазами
    if review:
        ws.cell(row=r, column=STATUS_COL).font = Font(bold=True, color="FF9C0006")
    r += 1

LAST = r - 1

ws.freeze_panes = ws.cell(row=FIRST, column=3)
ws.auto_filter.ref = f"A{SUB_ROW}:{get_column_letter(NCOL)}{LAST}"

ws.column_dimensions["A"].width = 30
ws.column_dimensions["B"].width = 40
for j in range(3, NCOL + 1):
    h = h1[j - 1]
    ws.column_dimensions[get_column_letter(j)].width = (
        42 if h in ("Отчёт 2026", "Отчёт 2025") else 14)
ws.row_dimensions[HEAD_ROW].height = 42
ws.row_dimensions[SUB_ROW].height = 18

# ─────────────── лист «Соответствие» ───────────────
ws2 = wb.create_sheet("Соответствие")
ws2.sheet_properties.tabColor = XL_LIGHT
ws2.append(["Код", "Название в рабочей таблице", "Форма", "Как считается"])
ws2.append(["2110", "Выручка, тыс.руб.", "ОФР", "значение кода 2110"])
ws2.append(["2300", "Прибыль до налогов, тыс.руб.", "ОФР", "значение кода 2300"])
ws2.append(["2330", "% к уплате", "ОФР", "значение кода 2330"])
ws2.append(["2320", "% к получению", "ОФР", "значение кода 2320"])
ws2.append(["1510", "Краткосрочный долг (до 1 года)", "Баланс", "значение кода 1510"])
ws2.append(["1550", "Прочие обяз., краткосрочные", "Баланс",
            "1550 + обязательство по аренде, если оно выделено отдельной строкой"])
ws2.append(["1410", "Долгосрочный долг (заёмные)", "Баланс", "значение кода 1410"])
ws2.append(["1450", "Прочие обяз., долгосрочные", "Баланс",
            "1450 + обязательство по аренде, если оно выделено отдельной строкой"])
ws2.append(["1250", "Денежные средства", "Баланс", "значение кода 1250"])
ws2.append(["1300", "Капитал", "Баланс", "значение кода 1300"])
ws2.append(["4100", "Сальдо ДП от текущих операций", "ОДДС", "значение кода 4100"])
ws2.append(["4110", "Поступления ДС из ОДДС", "ОДДС", "значение кода 4110"])

for j, w in enumerate([10, 40, 12, 62], start=1):
    ws2.column_dimensions[get_column_letter(j)].width = w
for c in ws2[1]:
    c.font, c.fill, c.alignment = HEAD_FONT, HEAD_FILL, CENTER
for row in ws2.iter_rows(min_row=2, max_row=ws2.max_row, max_col=4):
    for c in row:
        c.alignment = LEFT
        c.border = Border(bottom=thin)

# ─────────────── лист «Качество» ───────────────
ws3 = wb.create_sheet("Качество")
ws3.sheet_properties.tabColor = XL_LIGHT
ws3.append(["Строка рабочей таблицы", "Эмитент", "Отчёт 2025", "Отчёт 2026",
            "Заполнено значений", "Статус 2026", "Прочерков (заменены нулём)"])
for q in quality:
    ws3.append(q)
for j, w in enumerate([22, 42, 14, 14, 20, 16, 28], start=1):
    ws3.column_dimensions[get_column_letter(j)].width = w
for c in ws3[1]:
    c.font, c.fill, c.alignment = HEAD_FONT, HEAD_FILL, CENTER
for row in ws3.iter_rows(min_row=2, max_row=ws3.max_row, max_col=7):
    for c in row:
        c.border = Border(bottom=thin)
        c.alignment = LEFT if c.column <= 2 else CENTER
ws3.freeze_panes = "A2"
ws3.auto_filter.ref = f"A1:G{ws3.max_row}"

wb.properties.title = "Свод ВДО 9 мес 2025-2026"
# Файл может быть открыт в просмотрщике — тогда сохраняем рядом с отметкой времени,
# а не падаем и не затираем чужую копию молча.
import time
try:
    wb.save(OUT)
    saved = OUT
except PermissionError:
    base, ext = os.path.splitext(OUT)
    saved = f"{base}_{time.strftime('%Y%m%d_%H%M%S')}{ext}"
    wb.save(saved)
print("saved:", saved, "| строк данных:", LAST - FIRST + 1)
