#!/usr/bin/env python3
"""Detailed investigation of XLSX fill colors, legend."""
import sys
sys.path.insert(0, r"D:\models\pylibs")
import openpyxl

wb = openpyxl.load_workbook(r"D:\models\extracted\svod_2025_2026.xlsx", data_only=False)
ws = wb['Свод']

out = []

def pr(s=""):
    out.append(s)

pr("=== Row-by-row fill analysis ===\n")

for row_num in range(1, ws.max_row + 1):
    cell_a = ws.cell(row=row_num, column=1)
    val = cell_a.value
    fill = cell_a.fill

    fill_str = "none"
    if fill.patternType:
        fill_str = f"type={fill.patternType}"
        if fill.fgColor:
            fc = fill.fgColor
            fg = fc.rgb if fc.rgb else (f"theme={fc.theme}" if fc.theme is not None else f"indexed={fc.indexed}" if fc.indexed is not None else "?")
            fill_str += f", fg={fg}"

    bold = cell_a.font.bold if cell_a.font else False

    # Check col B fill
    bfc = ws.cell(row=row_num, column=2).fill
    b_fg = ""
    if bfc.patternType and bfc.fgColor:
        fc2 = bfc.fgColor
        if fc2.rgb and fc2.rgb != '00000000':
            b_fg = f"fg={fc2.rgb}"
        elif fc2.theme is not None:
            b_fg = f"theme={fc2.theme}"

    pr(f"Row {row_num:2d}: A={str(val):30s} bold={bold} A_fill=[{fill_str}] B_fill=[{b_fg}]")

pr("\n=== Legend rows (28-33) detail ===\n")
for row_num in range(28, 34):
    parts = []
    for col in range(1, min(ws.max_column + 1, 26)):
        c = ws.cell(row=row_num, column=col)
        v = c.value
        f2 = c.fill
        fill_info = ""
        if f2.patternType and f2.fgColor:
            fc2 = f2.fgColor
            if fc2.rgb and fc2.rgb != '00000000':
                fill_info = f"fg={fc2.rgb}"
            elif fc2.theme is not None:
                fill_info = f"theme={fc2.theme}"
            elif fc2.indexed is not None:
                fill_info = f"indexed={fc2.indexed}"
        if v is not None or fill_info:
            parts.append(f"Col{col}={v!r}[{fill_info}]")
    pr(f"Row {row_num}: {' | '.join(parts)}")

pr("\n=== Row 25 (Корпсан) — full cell detail ===\n")
for col in range(1, 26):
    c = ws.cell(row=25, column=col)
    f2 = c.fill
    if f2.patternType:
        fc = f2.fgColor
        detail = f"patternType={f2.patternType}"
        if fc:
            detail += f" fgType={fc.type}"
            if fc.rgb: detail += f" fgRgb={fc.rgb}"
            if fc.theme is not None: detail += f" fgTheme={fc.theme}"
            if fc.tint: detail += f" fgTint={fc.tint}"
            if fc.indexed is not None: detail += f" fgIndexed={fc.indexed}"
        bc = f2.bgColor
        if bc:
            detail += f" bgType={bc.type}"
            if bc.rgb: detail += f" bgRgb={bc.rgb}"
            if bc.theme is not None: detail += f" bgTheme={bc.theme}"
        pr(f"  Col {col}: {detail}")

pr("\n=== Row 26 (Рекорд трейд) — full cell detail ===\n")
for col in range(1, 26):
    c = ws.cell(row=26, column=col)
    f2 = c.fill
    if f2.patternType:
        fc = f2.fgColor
        detail = f"patternType={f2.patternType}"
        if fc:
            detail += f" fgType={fc.type}"
            if fc.rgb: detail += f" fgRgb={fc.rgb}"
            if fc.theme is not None: detail += f" fgTheme={fc.theme}"
            if fc.tint: detail += f" fgTint={fc.tint}"
            if fc.indexed is not None: detail += f" fgIndexed={fc.indexed}"
        bc = f2.bgColor
        if bc:
            detail += f" bgType={bc.type}"
            if bc.rgb: detail += f" bgRgb={bc.rgb}"
            if bc.theme is not None: detail += f" bgTheme={bc.theme}"
        pr(f"  Col {col}: {detail}")

# Check what the legend says in cols B/C/D etc
pr("\n=== Row 29 (legend item 1 — pink) full ===\n")
for col in range(1, 6):
    c = ws.cell(row=29, column=col)
    f2 = c.fill
    detail = f"val={c.value!r}"
    if f2.patternType:
        fc = f2.fgColor
        if fc:
            detail += f" fgRgb={fc.rgb}" if fc.rgb else f" fgTheme={fc.theme}" if fc.theme is not None else ""
    pr(f"  Col {col}: {detail}")

pr("\n=== Row 30 (legend item 2 — yellow) full ===\n")
for col in range(1, 6):
    c = ws.cell(row=30, column=col)
    f2 = c.fill
    detail = f"val={c.value!r}"
    if f2.patternType:
        fc = f2.fgColor
        if fc:
            detail += f" fgRgb={fc.rgb}" if fc.rgb else f" fgTheme={fc.theme}" if fc.theme is not None else ""
    pr(f"  Col {col}: {detail}")

pr("\n=== Row 31 (legend item 3 — dark gray) full ===\n")
for col in range(1, 6):
    c = ws.cell(row=31, column=col)
    f2 = c.fill
    detail = f"val={c.value!r}"
    if f2.patternType:
        fc = f2.fgColor
        if fc:
            detail += f" fgRgb={fc.rgb}" if fc.rgb else f" fgTheme={fc.theme}" if fc.theme is not None else ""
    pr(f"  Col {col}: {detail}")

pr("\n=== Row 32 (legend item 4 — light gray) full ===\n")
for col in range(1, 6):
    c = ws.cell(row=32, column=col)
    f2 = c.fill
    detail = f"val={c.value!r}"
    if f2.patternType:
        fc = f2.fgColor
        if fc:
            detail += f" fgRgb={fc.rgb}" if fc.rgb else f" fgTheme={fc.theme}" if fc.theme is not None else ""
    pr(f"  Col {col}: {detail}")

pr("\n=== Row 33 (Единица измерения) full ===\n")
for col in range(1, 6):
    c = ws.cell(row=33, column=col)
    pr(f"  Col {col}: val={c.value!r}")

with open(r"D:\models\_scope_detail_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
