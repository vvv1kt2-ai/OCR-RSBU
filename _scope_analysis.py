#!/usr/bin/env python3
"""
Scope analysis script — answers all 7 questions from the fact-finding task.
No files are modified. Output written to _scope_report.txt (UTF-8).
"""
import sys, os, csv, re, unicodedata
from pathlib import Path
from collections import OrderedDict

# Redirect all output to file
_report = open(r"D:\models\_scope_report.txt", "w", encoding="utf-8")
_orig_stdout = sys.stdout
_orig_print = print
def print(*args, **kwargs):
    kwargs.setdefault("file", _report)
    _orig_print(*args, **kwargs)

# ── 1. sum.csv ──────────────────────────────────────────────────────────────
print("=" * 80)
print("1. sum.csv — full list")
print("=" * 80)
sum_path = Path(r"D:\models\extracted\sum.csv")
with open(sum_path, encoding="utf-8") as f:
    reader = csv.reader(f)
    sum_header = next(reader)
    sum_rows = [r for r in reader]

print(f"Header (verbatim): {sum_header}")
print(f"Row count: {len(sum_rows)}")
for i, row in enumerate(sum_rows, 2):
    print(f"  Row {i}: {row[0]!r}  (cols: {len(row)})")

# ── 2. свод CSV vs XLSX emitter list ────────────────────────────────────────
print("\n" + "=" * 80)
print("2. Свод CSV — full emitter list")
print("=" * 80)
svod_csv_path = Path(r"D:\models\extracted\svod_2025_2026.csv")
with open(svod_csv_path, encoding="utf-8") as f:
    reader = csv.reader(f, delimiter=";")
    svod_csv_header = next(reader)
    svod_csv_rows = [r for r in reader]

print(f"Header (verbatim): {svod_csv_header}")
print(f"Row count: {len(svod_csv_rows)}")
svod_csv_emitters = []
for i, row in enumerate(svod_csv_rows, 2):
    name = row[0].strip()
    svod_csv_emitters.append(name)
    # Check if row has any non-empty data (not just semicolons)
    has_data = any(c.strip() for c in row[1:])
    print(f"  Row {i}: {name!r}  has_data={has_data}")

# ── 3. XLSX structural analysis ─────────────────────────────────────────────
print("\n" + "=" * 80)
print("3. XLSX structural analysis — 'Свод' sheet")
print("=" * 80)
sys.path.insert(0, r"D:\models\pylibs")
import openpyxl

wb = openpyxl.load_workbook(r"D:\models\extracted\svod_2025_2026.xlsx", data_only=False)
print(f"Sheet names: {wb.sheetnames}")

# Find the Свод sheet (might be slightly different name)
svod_sheet = None
for sname in wb.sheetnames:
    if "свод" in sname.lower():
        svod_sheet = wb[sname]
        break
if svod_sheet is None:
    svod_sheet = wb[wb.sheetnames[0]]
    print(f"WARNING: 'Свод' sheet not found, using first sheet: {svod_sheet.title}")
else:
    print(f"Using sheet: {svod_sheet.title!r}")

print(f"Dimensions: {svod_sheet.dimensions}")
print(f"Max row: {svod_sheet.max_row}, Max col: {svod_sheet.max_column}")
print(f"Merged cells: {list(svod_sheet.merged_cells.ranges)}")

# Column widths
print("\nColumn widths (non-default):")
for col_letter in [c for c in svod_sheet.column_dimensions]:
    dim = svod_sheet.column_dimensions[col_letter]
    if dim.width is not None and dim.width != 8:
        print(f"  Col {col_letter}: width={dim.width}")

# Row heights
print("\nRow heights (non-default):")
for row_num in svod_sheet.row_dimensions:
    dim = svod_sheet.row_dimensions[row_num]
    if dim.height is not None and dim.height != 15:
        print(f"  Row {row_num}: height={dim.height}")

# Read all rows verbatim — column A
print("\nVerbatim column A (all rows):")
xlsx_a_values = []
for row_num in range(1, svod_sheet.max_row + 1):
    cell = svod_sheet.cell(row=row_num, column=1)
    val = cell.value
    xlsx_a_values.append(val)
    fill = cell.fill
    font = cell.font
    comment = cell.comment
    fill_info = ""
    if fill and fill.fgColor and fill.fgColor.rgb and fill.fgColor.rgb != '00000000':
        fill_info = f" fill={fill.fgColor.rgb}"
    font_info = ""
    if font and font.bold:
        font_info = " BOLD"
    comment_info = ""
    if comment:
        comment_info = f" COMMENT={comment.text!r}"
    is_empty = val is None or (isinstance(val, str) and val.strip() == "")
    empty_marker = " [EMPTY]" if is_empty else ""
    print(f"  Row {row_num}: {val!r}{fill_info}{font_info}{comment_info}{empty_marker}")

# Deep cell analysis — check ALL cells in rows 1-max_row for formatting clues
print("\nDetailed cell analysis for rows with emitter names (checking fill colours, comments, fonts):")
emitter_fill_groups = {}
for row_num in range(1, svod_sheet.max_row + 1):
    cell_a = svod_sheet.cell(row=row_num, column=1)
    val = cell_a.value
    if val is None or (isinstance(val, str) and val.strip() == ""):
        continue
    fills = set()
    fonts_bold = set()
    comments = []
    for col_num in range(1, min(svod_sheet.max_column + 1, 30)):
        c = svod_sheet.cell(row=row_num, column=col_num)
        if c.fill and c.fill.fgColor and c.fill.fgColor.rgb and c.fill.fgColor.rgb != '00000000':
            fills.add(c.fill.fgColor.rgb)
        if c.font and c.font.bold:
            fonts_bold.add(col_num)
        if c.comment:
            comments.append(f"col{col_num}:{c.comment.text!r}")
    if fills or comments:
        print(f"  Row {row_num} {val!r}: fills={fills}, bold_cols={fonts_bold}, comments={comments}")

# ── 4. PDF files — group by emitter prefix ──────────────────────────────────
print("\n" + "=" * 80)
print("4. PDF files in downloads — grouped by emitter")
print("=" * 80)
dl_path = Path(r"D:\data-scraping\downloads")
all_pdfs = sorted(dl_path.glob("*.pdf"))
print(f"Total PDF files: {len(all_pdfs)}")

# Group PDFs by emitter name (strip _period_year suffix)
def emitter_from_pdf(pdf_name):
    """Extract emitter name from PDF filename."""
    stem = pdf_name.replace(".pdf", "")
    # Remove known suffixes
    for suffix in ["_6мес_2025", "_6мес_2026", "_год_2025", "_год_2026",
                    "_3мес_2025", "_3мес_2026", "_9мес_2025", "_9мес_2026"]:
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem  # fallback

pdf_by_emitter = {}
for pdf in all_pdfs:
    em = emitter_from_pdf(pdf.name)
    pdf_by_emitter.setdefault(em, []).append(pdf.name)

print(f"\nUnique emitter prefixes in PDFs: {len(pdf_by_emitter)}")
for em in sorted(pdf_by_emitter.keys()):
    files = sorted(pdf_by_emitter[em])
    print(f"  {em!r}: {files}")

# ── 5. JSON files — group by emitter prefix ─────────────────────────────────
print("\n" + "=" * 80)
print("5. JSON files in extracted — grouped by emitter (top-level only)")
print("=" * 80)
ext_path = Path(r"D:\models\extracted")
# Only top-level JSONs (not pages/)
top_jsons = [f for f in ext_path.glob("*.json") if f.parent == ext_path]
print(f"Total top-level JSON files: {len(top_jsons)}")

json_by_emitter = {}
for jf in sorted(top_jsons):
    stem = jf.stem
    # Match pattern: emitter_period_year
    for suffix in ["_6мес_2025", "_6мес_2026", "_год_2025", "_год_2026",
                    "_3мес_2025", "_3мес_2026", "_9мес_2025", "_9мес_2026"]:
        if stem.endswith(suffix):
            em = stem[: -len(suffix)]
            json_by_emitter.setdefault(em, []).append(jf.name)
            break
    else:
        json_by_emitter.setdefault(stem, []).append(jf.name)

print(f"Unique emitter prefixes in JSONs: {len(json_by_emitter)}")
for em in sorted(json_by_emitter.keys()):
    files = sorted(json_by_emitter[em])
    print(f"  {em!r}: {files}")

# ── 6. Cross-reference: свод emitters vs PDFs vs JSONs ──────────────────────
print("\n" + "=" * 80)
print("6. Cross-reference: свод emitters vs PDFs vs JSONs")
print("=" * 80)

# Build lookup sets
svod_emitters_set = set(svod_csv_emitters)
pdf_emitters_set = set(pdf_by_emitter.keys())
json_emitters_set = set(json_by_emitter.keys())

print(f"\nСвод emitters: {len(svod_emitters_set)}")
print(f"PDF emitter prefixes: {len(pdf_emitters_set)}")
print(f"JSON emitter prefixes: {len(json_emitters_set)}")

# Emitters in свод with NO PDF
svod_no_pdf = svod_emitters_set - pdf_emitters_set
print(f"\nEmitters in свод but NO PDF in downloads ({len(svod_no_pdf)}):")
for e in sorted(svod_no_pdf):
    print(f"  {e!r}")

# Emitters in PDF but NOT in свод
pdf_not_in_svod = pdf_emitters_set - svod_emitters_set
print(f"\nEmitters with PDFs but NOT in свод ({len(pdf_not_in_svod)}):")
for e in sorted(pdf_not_in_svod):
    print(f"  {e!r}: {sorted(pdf_by_emitter[e])}")

# Emitters in свod with NO JSON
svod_no_json = svod_emitters_set - json_emitters_set
print(f"\nEmitters in свод but NO top-level JSON ({len(svod_no_json)}):")
for e in sorted(svod_no_json):
    print(f"  {e!r}")

# Emitters in свod with JSON but no PDF (shouldn't happen, but check)
# Count PDFs per свод emitter
print(f"\nPDF count per свод emitter:")
for em in svod_csv_emitters:
    pdfs = pdf_by_emitter.get(em, [])
    jsons = json_by_emitter.get(em, [])
    print(f"  {em!r}: PDFs={len(pdfs)} ({[p.split('_')[-2]+'_'+p.split('_')[-1].replace('.pdf','') for p in pdfs]}), JSONs={len(jsons)}")

# ── 7. Totals ────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("7. Totals")
print("=" * 80)
print(f"Эмитенты in свод: {len(svod_csv_emitters)}")
# Count total PDFs that match свод emitters
svod_pdf_count = sum(len(pdf_by_emitter.get(em, [])) for em in svod_csv_emitters)
print(f"PDFs in scope for свод: {svod_pdf_count}")
print(f"Total PDFs in downloads: {len(all_pdfs)}")

# ── 8. Identify the ~20 group — all structural evidence ──────────────────────
print("\n" + "=" * 80)
print("8. Structural evidence for ~20 emitter grouping")
print("=" * 80)

# Count data rows vs empty/MСФО rows
data_rows = 0
empty_rows = 0
msfo_rows = 0
for i, row in enumerate(svod_csv_rows, 2):
    name = row[0].strip()
    has_data = any(c.strip() for c in row[1:])
    if "МСФО" in name:
        msfo_rows += 1
        print(f"  МСФО row: {i} {name!r} (data={has_data})")
    elif not has_data:
        empty_rows += 1
        print(f"  Empty data row: {i} {name!r}")
    else:
        data_rows += 1

print(f"\nData rows (non-empty, non-МСФО): {data_rows}")
print(f"Empty data rows: {empty_rows}")
print(f"МСФО rows: {msfo_rows}")
print(f"Total data rows including МСФО: {data_rows + msfo_rows}")

# ══════════════════════════════════════════════════════════════════════════════
# PART 2: Page classification for the 22-data-row emitters
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("9. PDF page classification for ALL свод emitters (using PyMuPDF)")
print("=" * 80)

import pymupdf

CYRILLIC_MIN_RATIO = 0.60
CHARS_MIN = 300

def classify_page(page):
    """Classify a PDF page as text-layer / garbled / no-text."""
    text = page.get_text("text")
    n_chars = len(text.strip())
    if n_chars < 50:
        return "no-text"
    # Count Cyrillic letters
    cyr_count = sum(1 for ch in text if '\u0400' <= ch <= '\u04FF')
    total_letters = sum(1 for ch in text if ch.isalpha())
    if total_letters == 0:
        return "no-text"
    cyr_ratio = cyr_count / total_letters
    if n_chars >= CHARS_MIN and cyr_ratio >= CYRILLIC_MIN_RATIO:
        return "text"
    else:
        return "garbled"

results = {}
for em in svod_csv_emitters:
    pdfs = pdf_by_emitter.get(em, [])
    em_stats = {"pages": 0, "text": 0, "garbled": 0, "no_text": 0, "files": []}
    for pdf_name in sorted(pdfs):
        pdf_path = dl_path / pdf_name
        try:
            doc = pymupdf.open(str(pdf_path))
            n_pages = len(doc)
            file_stats = {"pages": n_pages, "text": 0, "garbled": 0, "no_text": 0}
            for page in doc:
                cls = classify_page(page)
                if cls == "text":
                    file_stats["text"] += 1
                elif cls == "garbled":
                    file_stats["garbled"] += 1
                else:
                    file_stats["no_text"] += 1
            doc.close()
            em_stats["pages"] += file_stats["pages"]
            em_stats["text"] += file_stats["text"]
            em_stats["garbled"] += file_stats["garbled"]
            em_stats["no_text"] += file_stats["no_text"]
            em_stats["files"].append((pdf_name, file_stats))
        except Exception as ex:
            em_stats["files"].append((pdf_name, {"error": str(ex)}))
    results[em] = em_stats

# Print results
total_pages = total_text = total_garbled = total_no_text = 0
for em in svod_csv_emitters:
    s = results[em]
    total_pages += s["pages"]
    total_text += s["text"]
    total_garbled += s["garbled"]
    total_no_text += s["no_text"]
    file_details = []
    for fname, fs in s["files"]:
        if "error" in fs:
            file_details.append(f"{fname}: ERROR {fs['error']}")
        else:
            file_details.append(f"{fname}: {fs['pages']}p [T={fs['text']},G={fs['garbled']},N={fs['no_text']}]")
    print(f"  {em!r}: {s['pages']}p total [T={s['text']},G={s['garbled']},N={s['no_text']}]")
    for fd in file_details:
        print(f"    {fd}")

print(f"\nTOTALS for all {len(svod_csv_emitters)} свод emitters:")
print(f"  Pages: {total_pages}")
print(f"  Text pages: {total_text}")
print(f"  Scan/garbled pages: {total_garbled}")
print(f"  No-text pages: {total_no_text}")

_report.close()
sys.stdout = _orig_stdout
_orig_print("Report written to D:\\models\\_scope_report.txt")
