# Audit: Arithmetic Rules Completeness (RSBU pipeline)

Files scanned: 41
Documents with forms: 41

## Balance (Form 0710001) — All Rules

| Rule | LHS | RHS (in rule) | Missing children |
|------|-----|---------------|------------------|
| `1600 == 1700` | 1600 | 1700 | — (identity rule) |
| `1100 == 1110+1150+1160+1170+1180+1190` | 1100 | 1110, 1150, 1160, 1170, 1180, 1190 | — |
| **`1200 == 1210+1220+1230+1240+1250+1260`** | **1200** | 1210, 1220, 1230, 1240, 1250, 1260 | **1215** |
| `1300+1400+1500 == 1700` | 1300, 1400, 1500 | 1700 | — (totals rule) |

## Income Statement (Form 0710002) — All Rules

| Rule | LHS | RHS (in rule) | Type |
|------|-----|---------------|------|
| `2100 == 2110-2120 (±)` | 2100 | 2110, 2120 | derived |
| `2200 == 2100-2210-2220 (±)` | 2200 | 2100, 2210, 2220 | derived |
| `2300 == 2200+2310+2320-2330+2340-2350` (svod only) | 2300 | 2200, 2310, 2320, 2330, 2340, 2350 | derived |
| `2400 == 2300-2410±2421∓2430±2450-2460` | 2400 | 2300, 2410, 2421, 2430, 2450, 2460 | derived |

All income statement rules are structurally complete. The rules cover
the full sign-convention chain (2100→2200→2300→2400). No child codes
are missing from any rule.

**Note:** `pipeline.py` does not include the `2300` rule — it only has
rules for 2100, 2200, and 2400. `svod.py` adds the `2300` rule. This
is not a completeness gap in the rule itself, but a coverage gap between
the two files.

## Cash Flow (Form 0710005) — All Rules

| Rule | LHS | RHS (in rule) | Type |
|------|-----|---------------|------|
| `4100 == 4110-4120` | 4100 | 4110, 4120 | derived |
| `4200 == 4210-4220` | 4200 | 4210, 4220 | derived |
| `4300 == 4310-4320` | 4300 | 4310, 4320 | derived |
| `4400 == 4100+4200+4300` | 4400 | 4100, 4200, 4300 | sum of sections |
| `4500 == 4450+4400+4490` | 4500 | 4450, 4400, 4490 | sum of sections |

All cash flow rules are structurally complete. The `4111–4129`, `4211–4229`,
`4311–4329` codes are sub-detail lines (children of 4110/4120 etc.) that
are already folded into their parent totals by the extraction logic. No
codes that are direct components of 4100/4200/4300 are missing.

## Missing Codes — Detail

### Balance
**Rule: `1200 == 1210+1220+1230+1240+1250+1260`**

| Missing Code | Name | Docs with value |
|-------------|------|-----------------|
| 1215 | Долгосрочные активы к продаже | 4 |

### Income Statement
No missing child codes found.

### Cash Flow
No missing child codes found.

## Effect of Adding Missing Code 1215 to Balance Rule

### Rule: `1200 == 1210+1215+1220+1230+1240+1250+1260`

| Metric | Count |
|--------|-------|
| Documents failing before fix | 7 |
| Documents fixed by including 1215 | **3** |
| Documents still failing (other issues) | 4 |

**Fixed documents:**
- КЛВЗ Кристалл_6мес_2025
- КЛВЗ Кристалл_6мес_2026
- ТГК-14_6мес_2026

**Still failing (other extraction issues, not rule gap):**
- Корпсан_6мес_2026 — 1215 not in data; first column fails
- Моторные технологии_6мес_2025 — 1215 present but all None
- ТГК-14_6мес_2025 — 1215 present but residual > TOL in all columns
- Эфферон_6мес_2025 — 1215 present but all None

## Row Code Frequencies

### Balance (top codes, ≥5 docs with value)
| Code | Docs | With value |
|------|------|------------|
| 1100 | 40 | 40 |
| 1110 | 38 | 33 |
| 1150 | 41 | 41 |
| 1160 | 29 | 8 |
| 1170 | 36 | 27 |
| 1180 | 39 | 36 |
| 1190 | 36 | 23 |
| 1200 | 40 | 40 |
| 1210 | 40 | 40 |
| 1215 | 24 | 4 |
| 1220 | 37 | 31 |
| 1230 | 40 | 40 |
| 1240 | 38 | 30 |
| 1250 | 40 | 40 |
| 1260 | 40 | 38 |
| 1300 | 40 | 40 |
| 1310 | 40 | 40 |
| 1340 | 31 | 11 |
| 1350 | 30 | 13 |
| 1360 | 33 | 12 |
| 1370 | 40 | 40 |
| 1400 | 40 | 40 |
| 1410 | 40 | 40 |
| 1420 | 39 | 35 |
| 1430 | 31 | 5 |
| 1450 | 38 | 36 |
| 1500 | 40 | 40 |
| 1510 | 40 | 38 |
| 1520 | 40 | 40 |
| 1530 | 21 | 6 |
| 1540 | 40 | 40 |
| 1550 | 30 | 13 |
| 1600 | 40 | 40 |
| 1700 | 40 | 40 |

### Income Statement
| Code | Docs | With value |
|------|------|------------|
| 2100 | 27 | 27 |
| 2110 | 27 | 27 |
| 2120 | 27 | 26 |
| 2200 | 27 | 27 |
| 2210 | 26 | 22 |
| 2220 | 26 | 21 |
| 2300 | 27 | 27 |
| 2310 | 20 | 1 |
| 2320 | 27 | 27 |
| 2330 | 27 | 27 |
| 2340 | 27 | 27 |
| 2350 | 27 | 27 |
| 2400 | 27 | 27 |
| 2410 | 26 | 24 |
| 2460 | 9 | 3 |
| 2500 | 25 | 25 |

### Cash Flow
| Code | Docs | With value |
|------|------|------------|
| 4100 | 23 | 23 |
| 4110 | 23 | 23 |
| 4120 | 23 | 23 |
| 4200 | 23 | 23 |
| 4210 | 23 | 19 |
| 4220 | 23 | 23 |
| 4300 | 23 | 23 |
| 4310 | 23 | 22 |
| 4320 | 23 | 23 |
| 4400 | 23 | 23 |
| 4450 | 23 | 23 |
| 4490 | 20 | 9 |
| 4500 | 23 | 23 |

## Conclusion

### Confirmed gap: Balance rule `1200` is incomplete

Row 1215 ("Долгосрочные активы к продаже") is a legitimate child of
section II total (1200) per RSBU Form 0710001. It is present in
extracted data (4 docs with values) but absent from the rule in both
`pipeline.py` (line ~392) and `svod.py` (line ~121).

**Impact:** Adding 1215 to the rule fixes 3 out of 7 currently-failing
documents (КЛВЗ Кристалл ×2, ТГК-14_2026). The remaining 4 failures
are due to other extraction issues (missing or null 1215 values, or
other residual mismatches exceeding TOL=2).

### Other forms: no structural gaps found

- **Income Statement:** All derived rules (2100→2200→2300→2400) cover
  the complete chain. `pipeline.py` omits the `2300` rule that `svod.py`
  has — this is a coverage gap, not a rule-completeness gap.
- **Cash Flow:** All rules (4100/4200/4300 derived, 4400 and 4500 sums)
  are complete. Sub-detail codes (4111–4329) are correctly folded into
  parent totals by extraction.

### Fix locations

1. `pipeline.py` line ~392: change rule to
   `1200 == 1210+1215+1220+1230+1240+1250+1260`
2. `svod.py` line ~121: change rule to
   `1200 == 1210+1215+1220+1230+1240+1250+1260`
