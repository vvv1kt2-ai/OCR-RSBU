# -*- coding: utf-8 -*-
"""Audit: find incomplete arithmetic rules in pipeline.py / svod.py.

Scans extracted/*.json, collects all row codes with non-empty values,
cross-references against rules, identifies missing child codes per rule,
and estimates the effect of fixing the rules.

Key distinction: for a rule like `1200 == 1210+1220+…+1260`, we look
for codes that are DIRECT CHILDREN of 1200 in the form hierarchy but
are missing from the RHS. For a rule like `1300+1400+1500 == 1700`,
the children of 1300/1400/1500 are NOT relevant — it's a totals rule.
"""
import sys
import json
import os
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, 'D:/models')
sys.path.insert(0, 'D:/models/pylibs')

# ── 1. Discover all extracted JSON files (NOT starting with _) ───────
EXTRACTED = Path('D:/models/extracted')
files = sorted(f for f in EXTRACTED.glob('*.json') if not f.name.startswith('_'))
print(f"[info] Found {len(files)} extracted JSON files")

# ── 2. Load and collect codes per form ────────────────────────────────
codes_balance = defaultdict(dict)   # code -> { doc_name: [values] }
codes_income = defaultdict(dict)
codes_cashflow = defaultdict(dict)
doc_forms = {}  # doc_name -> set of form keys present
doc_form_data = {}  # doc_name -> { form_key: form_data }

for fpath in files:
    doc_name = fpath.stem
    try:
        data = json.loads(fpath.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"[warn] Cannot parse {fpath.name}: {e}")
        continue
    doc_form_data[doc_name] = {}
    for form_key, storage in [
        ('balance', codes_balance),
        ('income_statement', codes_income),
        ('cash_flow', codes_cashflow),
    ]:
        form = data.get(form_key)
        if not form or not form.get('items'):
            continue
        if doc_name not in doc_forms:
            doc_forms[doc_name] = set()
        doc_forms[doc_name].add(form_key)
        doc_form_data[doc_name][form_key] = form
        for it in form['items']:
            code = it.get('code')
            vals = it.get('values')
            if code and vals:
                storage[code][doc_name] = vals

print(f"[info] Documents with forms: {len(doc_forms)}")

# ── 3. Build hierarchy ───────────────────────────────────────────────
def build_parent_child(codes_map):
    parents = defaultdict(set)
    for code in codes_map:
        if len(code) == 4 and code.endswith('00'):
            prefix = code[:2]
            for child_code in codes_map:
                if child_code.startswith(prefix) and child_code != code and len(child_code) == 4:
                    parents[code].add(child_code)
    return parents

parents_b = build_parent_child(codes_balance)
parents_i = build_parent_child(codes_income)
parents_c = build_parent_child(codes_cashflow)

# ── 4. Define rules ─────────────────────────────────────────────────
BALANCE_RULES = [
    {
        'name': '1600 == 1700',
        'lhs': ['1600'],
        'rhs': ['1700'],
        'type': 'identity',
    },
    {
        'name': '1100 == 1110+1150+1160+1170+1180+1190',
        'lhs': ['1100'],
        'rhs': ['1110', '1150', '1160', '1170', '1180', '1190'],
        'type': 'sum_of_children',
        'parent_code': '1100',
    },
    {
        'name': '1200 == 1210+1220+1230+1240+1250+1260',
        'lhs': ['1200'],
        'rhs': ['1210', '1220', '1230', '1240', '1250', '1260'],
        'type': 'sum_of_children',
        'parent_code': '1200',
    },
    {
        'name': '1300+1400+1500 == 1700',
        'lhs': ['1300', '1400', '1500'],
        'rhs': ['1700'],
        'type': 'totals_sum',
    },
]

INCOME_RULES = [
    {
        'name': '2100 == 2110-2120 (±)',
        'lhs': ['2100'],
        'rhs': ['2110', '2120'],
        'type': 'derived',
    },
    {
        'name': '2200 == 2100-2210-2220 (±)',
        'lhs': ['2200'],
        'rhs': ['2100', '2210', '2220'],
        'type': 'derived',
    },
    {
        'name': '2300 == 2200+2310+2320-2330+2340-2350 (svod only)',
        'lhs': ['2300'],
        'rhs': ['2200', '2310', '2320', '2330', '2340', '2350'],
        'type': 'derived',
    },
    {
        'name': '2400 == 2300-2410±2421∓2430±2450-2460',
        'lhs': ['2400'],
        'rhs': ['2300', '2410', '2421', '2430', '2450', '2460'],
        'type': 'derived',
    },
]

CASHFLOW_RULES = [
    {
        'name': '4100 == 4110-4120',
        'lhs': ['4100'],
        'rhs': ['4110', '4120'],
        'type': 'derived',
    },
    {
        'name': '4200 == 4210-4220',
        'lhs': ['4200'],
        'rhs': ['4210', '4220'],
        'type': 'derived',
    },
    {
        'name': '4300 == 4310-4320',
        'lhs': ['4300'],
        'rhs': ['4310', '4320'],
        'type': 'derived',
    },
    {
        'name': '4400 == 4100+4200+4300',
        'lhs': ['4400'],
        'rhs': ['4100', '4200', '4300'],
        'type': 'sum_of_children',
        'parent_code': '4400',
    },
    {
        'name': '4500 == 4450+4400+4490',
        'lhs': ['4500'],
        'rhs': ['4450', '4400', '4490'],
        'type': 'sum_of_children',
        'parent_code': '4500',
    },
]

# ── 5. Find missing child codes for sum_of_children rules ───────────
def find_missing_for_sum_rules(rules, codes_map, parents_map):
    results = []
    for rule in rules:
        if rule['type'] != 'sum_of_children':
            continue
        parent = rule['parent_code']
        rhs_set = set(rule['rhs'])
        known_children = parents_map.get(parent, set())
        missing = {}
        # Check known children not in RHS
        for child in sorted(known_children):
            if child not in rhs_set and child in codes_map:
                n_val = sum(1 for v in codes_map[child].values()
                            if any(x is not None for x in v))
                if n_val > 0:
                    missing[child] = n_val
        # Check unknown children (codes in data with same prefix)
        prefix = parent[:2]
        for code in sorted(codes_map.keys()):
            if code.startswith(prefix) and code != parent and code not in rhs_set and code not in known_children:
                n_val = sum(1 for v in codes_map[code].values()
                            if any(x is not None for x in v))
                if n_val > 0:
                    missing[code] = n_val
        if missing:
            results.append({'rule': rule['name'], 'missing': missing, 'parent': parent})
    return results

missing_b = find_missing_for_sum_rules(BALANCE_RULES, codes_balance, parents_b)
missing_i = find_missing_for_sum_rules(INCOME_RULES, codes_income, parents_i)
missing_c = find_missing_for_sum_rules(CASHFLOW_RULES, codes_cashflow, parents_c)

# ── 6. Effect estimation: simulate fixing the RULE ──────────────────
TOL = 2

def val_map_from_items(items):
    m = {}
    for it in items:
        c = it.get('code')
        if c:
            m[c] = it.get('values')
    return m

def simulate_balance_rule_with_extra_codes(doc_name, form_data, extra_rhs_codes):
    """Re-check the 1200 rule with extra codes added to RHS."""
    items = form_data.get('items', [])
    m = val_map_from_items(items)
    n = max((len(it.get('values') or []) for it in items if it.get('values')), default=0)

    def S(code, c):
        v = m.get(code)
        if v is None or c >= len(v):
            return None
        return v[c]

    def nz(*xs):
        return sum(x for x in xs if x is not None)

    def has(*xs):
        return any(x is not None for x in xs)

    def eq(a, b):
        return a is not None and b is not None and abs(a - b) <= TOL

    # Original RHS
    orig_rhs = ['1210', '1220', '1230', '1240', '1250', '1260']
    # Extended RHS
    ext_rhs = orig_rhs + list(extra_rhs_codes)

    # Check original
    orig_ok = True
    orig_has_any = False
    for c in range(n):
        lhs_val = S('1200', c)
        if lhs_val is None:
            continue
        rhs_sum = nz(*[S(k, c) for k in orig_rhs])
        if lhs_val is not None and rhs_sum is not None:
            orig_has_any = True
            if not eq(lhs_val, rhs_sum):
                orig_ok = False
                break

    # Check extended
    ext_ok = True
    ext_has_any = False
    for c in range(n):
        lhs_val = S('1200', c)
        if lhs_val is None:
            continue
        rhs_sum = nz(*[S(k, c) for k in ext_rhs])
        if lhs_val is not None and rhs_sum is not None:
            ext_has_any = True
            if not eq(lhs_val, rhs_sum):
                ext_ok = False
                break

    return {
        'orig_ok': orig_ok if orig_has_any else None,
        'ext_ok': ext_ok if ext_has_any else None,
        'orig_has_any': orig_has_any,
        'ext_has_any': ext_has_any,
    }


def estimate_balance_effect(missing_list):
    results = []
    for mi in missing_list:
        rule_name = mi['rule']
        extra_codes = list(mi['missing'].keys())
        fixed_docs = []
        still_failing_docs = []
        not_affected_docs = []

        for doc_name, forms in doc_form_data.items():
            bal = forms.get('balance')
            if not bal:
                continue

            # Use the appropriate simulation based on the rule
            if '1200' in rule_name:
                result = simulate_balance_rule_with_extra_codes(doc_name, bal, extra_codes)
            else:
                # For other rules, skip detailed simulation for now
                continue

            if result['orig_ok'] is None or not result['orig_has_any']:
                continue  # rule not applicable

            if result['orig_ok']:
                continue  # already passing

            # Document is failing
            if result['ext_ok']:
                fixed_docs.append(doc_name)
            else:
                still_failing_docs.append(doc_name)

        results.append({
            'rule': rule_name,
            'missing_codes': extra_codes,
            'missing_n_docs': mi['missing'],
            'fixed_docs': fixed_docs,
            'still_failing_docs': still_failing_docs,
        })
    return results

effect_b = estimate_balance_effect(missing_b)

# ── 7. Also check income/cashflow for structural issues ─────────────
# For derived rules, check if there are 4-digit codes in the same section
# that are NOT in the rule and could be relevant
def find_derived_rule_gaps(rules, codes_map):
    """For derived rules, look for codes that might be missing components."""
    results = []
    for rule in rules:
        if rule['type'] != 'derived':
            continue
        # Collect all 4-digit codes that share a prefix with any RHS code
        all_rhs_prefixes = set()
        for code in rule['rhs']:
            all_rhs_prefixes.add(code[:2])

        related_codes = set()
        for code in codes_map:
            if len(code) == 4 and code[:2] in all_rhs_prefixes:
                if code not in set(rule['rhs']) and code not in set(rule['lhs']):
                    n_val = sum(1 for v in codes_map[code].values()
                                if any(x is not None for x in v))
                    if n_val > 0:
                        related_codes.add(code)

        if related_codes:
            results.append({
                'rule': rule['name'],
                'related_codes_not_in_rule': sorted(related_codes),
            })
    return results

gap_i = find_derived_rule_gaps(INCOME_RULES, codes_income)
gap_c = find_derived_rule_gaps(CASHFLOW_RULES, codes_cashflow)

# ── 8. Code frequency tables ─────────────────────────────────────────
def code_stats(codes_map):
    lines = []
    for code in sorted(codes_map.keys()):
        n_docs = len(codes_map[code])
        n_val = sum(1 for v in codes_map[code].values()
                    if any(x is not None for x in v))
        lines.append((code, n_docs, n_val))
    return lines

stats_b = code_stats(codes_balance)
stats_i = code_stats(codes_income)
stats_c = code_stats(codes_cashflow)

# ── 9. Write report ──────────────────────────────────────────────────
report = []
report.append('# Audit: Arithmetic Rules Completeness (RSBU pipeline)')
report.append('')
report.append(f'Files scanned: {len(files)}')
report.append(f'Documents with forms: {len(doc_forms)}')
report.append('')

# Section: balance rules
report.append('## Balance (Form 0710001) — All Rules')
report.append('')
report.append('| Rule | LHS | RHS (in rule) | Missing children |')
report.append('|------|-----|---------------|------------------|')
for rule in BALANCE_RULES:
    missing_for_rule = next((m for m in missing_b if m['rule'] == rule['name']), None)
    missing_str = ', '.join(sorted(missing_for_rule['missing'].keys())) if missing_for_rule else '—'
    report.append(f'| `{rule["name"]}` | {", ".join(rule["lhs"])} | {", ".join(rule["rhs"])} | {missing_str} |')
report.append('')

# Section: income rules
report.append('## Income Statement (Form 0710002) — All Rules')
report.append('')
report.append('| Rule | LHS | RHS (in rule) | Type |')
report.append('|------|-----|---------------|------|')
for rule in INCOME_RULES:
    report.append(f'| `{rule["name"]}` | {", ".join(rule["lhs"])} | {", ".join(rule["rhs"])} | derived |')
report.append('')

# Section: cash flow rules
report.append('## Cash Flow (Form 0710005) — All Rules')
report.append('')
report.append('| Rule | LHS | RHS (in rule) | Type |')
report.append('|------|-----|---------------|------|')
for rule in CASHFLOW_RULES:
    report.append(f'| `{rule["name"]}` | {", ".join(rule["lhs"])} | {", ".join(rule["rhs"])} | {rule["type"]} |')
report.append('')

# Section: missing code details
report.append('## Missing Codes — Detail')
report.append('')
for label, missing_list in [('Balance', missing_b), ('Income Statement', missing_i), ('Cash Flow', missing_c)]:
    report.append(f'### {label}')
    if not missing_list:
        report.append('No missing child codes found in sum-of-children rules.')
    else:
        for mi in missing_list:
            report.append(f'**Rule: `{mi["rule"]}`**')
            report.append('')
            report.append('| Missing Code | Docs with value |')
            report.append('|-------------|-----------------|')
            for code, n in sorted(mi['missing'].items()):
                report.append(f'| {code} | {n} |')
            report.append('')
    report.append('')

# Section: income/cashflow related codes
report.append('## Related Codes Not in Derived Rules')
report.append('')
for label, gaps in [('Income Statement', gap_i), ('Cash Flow', gap_c)]:
    report.append(f'### {label}')
    if not gaps:
        report.append('No related codes outside rules.')
    else:
        for g in gaps:
            report.append(f'- Rule `{g["rule"]}`: related codes not in rule: {", ".join(g["related_codes_not_in_rule"])}')
    report.append('')

# Section: effect
report.append('## Effect of Adding Missing Codes (Balance)')
report.append('')
if not effect_b:
    report.append('No balance rules with missing children found.')
else:
    for eff in effect_b:
        report.append(f'### Rule: `{eff["rule"]}`')
        report.append(f'- Missing codes: {", ".join(eff["missing_codes"])}')
        total_failing = len(eff['fixed_docs']) + len(eff['still_failing_docs'])
        report.append(f'- Documents failing before: {total_failing}')
        report.append(f'- Documents fixed by inclusion: {len(eff["fixed_docs"])}')
        report.append(f'- Documents still failing after: {len(eff["still_failing_docs"])}')
        if eff['fixed_docs']:
            report.append(f'- Fixed docs: {", ".join(eff["fixed_docs"])}')
        if eff['still_failing_docs']:
            report.append(f'- Still failing: {", ".join(eff["still_failing_docs"])}')
        report.append('')

# Section: code frequency
report.append('## Row Code Frequencies')
report.append('')
for label, stats in [('Balance', stats_b), ('Income Statement', stats_i), ('Cash Flow', stats_c)]:
    report.append(f'### {label}')
    report.append('| Code | Docs with code | Docs with value |')
    report.append('|------|---------------|-----------------|')
    for code, n_doc, n_val in stats:
        report.append(f'| {code} | {n_doc} | {n_val} |')
    report.append('')

# Conclusion
report.append('## Conclusion')
report.append('')
report.append('### Key finding: Balance rule `1200 == 1210+…+1260`')
report.append('')
report.append('Row 1215 ("Долгосрочные активы к продаже") is a legitimate child of')
report.append('section II total (1200) per RSBU Form 0710001. It is present in')
report.append('extracted data but absent from the rule in both `pipeline.py` (line ~392)')
report.append('and `svod.py` (line ~121).')
report.append('')
for eff in effect_b:
    if '1200' in eff['rule']:
        report.append(f'- Code 1215 filled in {eff["missing_n_docs"].get("1215", "?")} documents')
        report.append(f'- Documents failing rule before fix: {len(eff["fixed_docs"]) + len(eff["still_failing_docs"])}')
        report.append(f'- Documents fixed by including 1215: {len(eff["fixed_docs"])}')
        if eff['fixed_docs']:
            report.append(f'- Fixed: {", ".join(eff["fixed_docs"])}')
        if eff['still_failing_docs']:
            report.append(f'- Still failing (other issues): {", ".join(eff["still_failing_docs"])}')
report.append('')
report.append('### Other forms')
report.append('')
if gap_i:
    report.append('Income Statement: related codes found outside rules (see above).')
    report.append('These are `derived` rules with sign conventions — the effect analysis')
    report.append('requires careful sign handling.')
else:
    report.append('Income Statement: all rule RHS codes cover observed data codes.')
report.append('')
if gap_c:
    report.append('Cash Flow: related codes found outside rules (see above).')
else:
    report.append('Cash Flow: all rule RHS codes cover observed data codes.')
report.append('')
report.append('### Fix locations')
report.append('')
report.append('- `pipeline.py` line ~392: add `1215` to the rule for `1200`')
report.append('- `svod.py` line ~121: add `1215` to the rule for `1200`')
report.append('')

out_path = Path('D:/models/_rules_audit.md')
out_path.write_text('\n'.join(report), encoding='utf-8')
print(f"\n[done] Report written to {out_path}")

# ── 10. Print concise summary to stdout ─────────────────────────────
print("\n=== SUMMARY ===")
print(f"Files scanned: {len(files)}, Documents: {len(doc_forms)}")
print()
for eff in effect_b:
    print(f"Rule: {eff['rule']}")
    print(f"  Missing: {', '.join(eff['missing_codes'])}")
    total = len(eff['fixed_docs']) + len(eff['still_failing_docs'])
    print(f"  Failing before: {total}")
    print(f"  Fixed by inclusion: {len(eff['fixed_docs'])}")
    if eff['fixed_docs']:
        print(f"  Fixed docs: {', '.join(eff['fixed_docs'][:10])}")
    print()
print(f"Balance rules with gaps: {len(missing_b)}")
print(f"Income rules with gaps: {len(missing_i)}")
print(f"Cashflow rules with gaps: {len(missing_c)}")
if gap_i:
    print(f"Income derived rules with related codes outside: {len(gap_i)}")
if gap_c:
    print(f"Cashflow derived rules with related codes outside: {len(gap_c)}")
