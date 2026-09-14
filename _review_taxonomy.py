#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Fact-finding report: classify why each needs_review document failed its checks.
Reads JSON files from D:\models\extracted\ and escalation artifacts from
D:\models\extracted\pages\.  Produces a table to stdout.
"""
import json, os, sys, glob, re
from collections import defaultdict

OUTDIR = r'D:\models\extracted'
PAGESDIR = os.path.join(OUTDIR, 'pages')

# The 11 documents with status needs_review
NEEDS_REVIEW = [
    'КИФА_6мес_2026',
    'КЛВЗ Кристалл_6мес_2025',
    'КЛВЗ Кристалл_6мес_2026',
    'Корпсан_6мес_2026',
    'Моторные технологии_6мес_2025',
    'Органик парк_6мес_2025',
    'Проект 111_6мес_2025',
    'Проект 111_6мес_2026',
    'ТГК-14_6мес_2025',
    'ТГК-14_6мес_2026',
    'Эфферон_6мес_2025',
]

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def val_map_from_items(items):
    """Build code -> values list from top-level items."""
    m = {}
    for it in items:
        if it.get('code'):
            m[it['code']] = it.get('values', [])
    return m

def find_esc_artifacts(doc_name):
    """Find all pdf_esc and tstruct artifacts for a document."""
    prefix = os.path.splitext(doc_name)[0]
    pdf_esc = []
    tstruct = []
    for f in glob.glob(os.path.join(PAGESDIR, f'_llm_{prefix}*.json')):
        basename = os.path.basename(f)
        if 'pdf_esc' in basename:
            pdf_esc.append(f)
        elif 'tstruct' in basename:
            tstruct.append(f)
    return pdf_esc, tstruct

def read_esc_verdict(pdf_esc_path):
    """Read escalation artifact and report what the stronger model found."""
    try:
        data = load_json(pdf_esc_path)
    except Exception as e:
        return f"FAILED TO READ: {e}"
    return data

def compute_1200_discrepancy(balance_items):
    """Compute the actual discrepancy for 1200 == 1210+1220+1230+1240+1250+1260."""
    m = val_map_from_items(balance_items)
    codes = ['1210', '1220', '1230', '1240', '1250', '1260']
    vals_1200 = m.get('1200', [])
    n = max((len(v) for v in [vals_1200] + [m.get(c, []) for c in codes]), default=0)
    results = []
    for c in range(n):
        actual = vals_1200[c] if c < len(vals_1200) else None
        expected_parts = {}
        exp_sum = 0
        for code in codes:
            cv = m.get(code, [])
            v = cv[c] if c < len(cv) else None
            if v is not None:
                expected_parts[code] = v
                exp_sum += v
            else:
                expected_parts[code] = None
        if actual is not None and exp_sum != 0:
            diff = actual - exp_sum
            rel = abs(diff / exp_sum) if exp_sum != 0 else 0
            results.append((actual, exp_sum, diff, rel))
        else:
            results.append((actual, exp_sum, None, None))
    return results

def compute_1100_discrepancy(balance_items):
    """Compute discrepancy for 1100 == 1110+1150+1160+1170+1180+1190."""
    m = val_map_from_items(balance_items)
    codes = ['1110', '1150', '1160', '1170', '1180', '1190']
    vals_1100 = m.get('1100', [])
    n = max((len(v) for v in [vals_1100] + [m.get(c, []) for c in codes]), default=0)
    results = []
    for c in range(n):
        actual = vals_1100[c] if c < len(vals_1100) else None
        exp_sum = 0
        for code in codes:
            cv = m.get(code, [])
            v = cv[c] if c < len(cv) else None
            if v is not None:
                exp_sum += v
        if actual is not None and exp_sum != 0:
            diff = actual - exp_sum
            rel = abs(diff / exp_sum) if exp_sum != 0 else 0
            results.append((actual, exp_sum, diff, rel))
        else:
            results.append((actual, exp_sum, None, None))
    return results

def compute_1600_1700_discrepancy(balance_items):
    """Compute discrepancy for 1600 == 1700."""
    m = val_map_from_items(balance_items)
    vals_1600 = m.get('1600', [])
    vals_1700 = m.get('1700', [])
    n = max(len(vals_1600), len(vals_1700), 0)
    results = []
    for c in range(n):
        a = vals_1600[c] if c < len(vals_1600) else None
        b = vals_1700[c] if c < len(vals_1700) else None
        if a is not None and b is not None:
            diff = a - b
            rel = abs(diff / b) if b != 0 else 0
            results.append((a, b, diff, rel))
        else:
            results.append((a, b, None, None))
    return results

def compute_1300_1400_1500_1700_discrepancy(balance_items):
    """Compute discrepancy for 1300+1400+1500 == 1700."""
    m = val_map_from_items(balance_items)
    vals_1700 = m.get('1700', [])
    n = len(vals_1700)
    results = []
    for c in range(n):
        left = 0
        for code in ['1300', '1400', '1500']:
            cv = m.get(code, [])
            v = cv[c] if c < len(cv) else None
            if v is not None:
                left += v
        right = vals_1700[c] if c < len(vals_1700) else None
        if left != 0 and right is not None:
            diff = left - right
            rel = abs(diff / right) if right != 0 else 0
            results.append((left, right, diff, rel))
        else:
            results.append((left, right, None, None))
    return results

def compute_2100_discrepancy(income_items):
    """2100 == 2110-2120 (with sign tolerance)."""
    m = val_map_from_items(income_items)
    vals_2100 = m.get('2100', [])
    n = len(vals_2100)
    results = []
    for c in range(n):
        actual = vals_2100[c] if c < len(vals_2100) else None
        v2110 = (m.get('2110', []) or [None]*(c+1))[c] if c < len(m.get('2110', [])) else None
        v2120 = (m.get('2120', []) or [None]*(c+1))[c] if c < len(m.get('2120', [])) else None
        if v2110 is not None and v2120 is not None:
            expected = v2110 - abs(v2120)
        elif v2110 is not None:
            expected = v2110
        else:
            expected = None
        if actual is not None and expected is not None:
            diff = actual - expected
            rel = abs(diff / expected) if expected != 0 else 0
            results.append((actual, expected, diff, rel))
        else:
            results.append((actual, expected, None, None))
    return results

def compute_2400_discrepancy(income_items):
    """2400 == 2300-2410+2421-2430+2450-2460 (with sign tolerance)."""
    m = val_map_from_items(income_items)
    vals_2400 = m.get('2400', [])
    n = len(vals_2400)
    results = []
    for c in range(n):
        actual = vals_2400[c] if c < len(vals_2400) else None
        parts = {}
        for code in ['2300', '2410', '2421', '2430', '2450', '2460']:
            cv = m.get(code, [])
            parts[code] = cv[c] if c < len(cv) else None
        v2300 = parts.get('2300') or 0
        v2410 = parts.get('2410') or 0
        v2421 = parts.get('2421') or 0
        v2430 = parts.get('2430') or 0
        v2450 = parts.get('2450') or 0
        v2460 = parts.get('2460') or 0
        expected = v2300 - v2410 + v2421 - v2430 + v2450 - v2460
        if actual is not None and expected != 0:
            diff = actual - expected
            rel = abs(diff / expected) if expected != 0 else 0
            results.append((actual, expected, diff, rel))
        else:
            results.append((actual, expected, None, None))
    return results

def compute_4400_discrepancy(cash_items):
    """4400 == 4100+4200+4300."""
    m = val_map_from_items(cash_items)
    vals_4400 = m.get('4400', [])
    n = len(vals_4400)
    results = []
    for c in range(n):
        actual = vals_4400[c] if c < len(vals_4400) else None
        parts = []
        for code in ['4100', '4200', '4300']:
            cv = m.get(code, [])
            v = cv[c] if c < len(cv) else None
            if v is not None:
                parts.append(v)
        expected = sum(parts) if parts else None
        if actual is not None and expected is not None:
            diff = actual - expected
            rel = abs(diff / expected) if expected != 0 else 0
            results.append((actual, expected, diff, rel))
        else:
            results.append((actual, expected, None, None))
    return results

def compute_4500_discrepancy(cash_items):
    """4500 == 4450+4400+4490."""
    m = val_map_from_items(cash_items)
    vals_4500 = m.get('4500', [])
    n = len(vals_4500)
    results = []
    for c in range(n):
        actual = vals_4500[c] if c < len(vals_4500) else None
        parts = []
        for code in ['4450', '4400', '4490']:
            cv = m.get(code, [])
            v = cv[c] if c < len(cv) else None
            if v is not None:
                parts.append(v)
        expected = sum(parts) if parts else None
        if actual is not None and expected is not None:
            diff = actual - expected
            rel = abs(diff / expected) if expected != 0 else 0
            results.append((actual, expected, diff, rel))
        else:
            results.append((actual, expected, None, None))
    return results

def check_1700_present(balance_items):
    """Check if code 1700 is present in balance items."""
    m = val_map_from_items(balance_items)
    return '1700' in m

def check_1300_1400_1500_present(balance_items):
    """Check if codes 1300, 1400, 1500 are present."""
    m = val_map_from_items(balance_items)
    return all(c in m for c in ['1300', '1400', '1500'])

def analyze_document(doc_name):
    """Analyze one document and return structured findings."""
    path = os.path.join(OUTDIR, doc_name + '.json')
    data = load_json(path)
    
    findings = {
        'name': doc_name,
        'status': data.get('status'),
        'warnings': data.get('warnings', []),
        'failed_checks': [],
        'escalation_artifacts': [],
        'escalation_verdict': None,
        'discrepancies': {},
    }
    
    # Extract failed checks from top-level checks array
    checks = data.get('checks', [])
    for chk in checks:
        if not chk.get('ok', True):
            findings['failed_checks'].append({
                'form': chk['form'],
                'rule': chk['rule'],
                'per_column': chk['per_column'],
            })
    
    # Compute numeric discrepancies
    balance = data.get('balance') or {}
    income = data.get('income_statement') or {}
    cash = data.get('cash_flow') or {}
    
    balance_items = balance.get('items', [])
    income_items = income.get('items', [])
    cash_items = cash.get('items', [])
    
    has_1700 = check_1700_present(balance_items)
    has_1300_1400_1500 = check_1300_1400_1500_present(balance_items)
    
    for chk in findings['failed_checks']:
        rule = chk['rule']
        form = chk['form']
        if rule == '1200 == 1210+1220+1230+1240+1250+1260' and balance_items:
            disc = compute_1200_discrepancy(balance_items)
            findings['discrepancies'][rule] = disc
        elif rule == '1100 == 1110+1150+1160+1170+1180+1190' and balance_items:
            disc = compute_1100_discrepancy(balance_items)
            findings['discrepancies'][rule] = disc
        elif rule == '1600 == 1700' and balance_items:
            disc = compute_1600_1700_discrepancy(balance_items)
            findings['discrepancies'][rule] = disc
        elif rule == '1300+1400+1500 == 1700' and balance_items:
            disc = compute_1300_1400_1500_1700_discrepancy(balance_items)
            findings['discrepancies'][rule] = disc
        elif rule == '2100 == 2110-2120 (±)' and income_items:
            disc = compute_2100_discrepancy(income_items)
            findings['discrepancies'][rule] = disc
        elif rule == '2400 == 2300-2410±2421∓2430±2450-2460' and income_items:
            disc = compute_2400_discrepancy(income_items)
            findings['discrepancies'][rule] = disc
        elif rule == '4400 == 4100+4200+4300' and cash_items:
            disc = compute_4400_discrepancy(cash_items)
            findings['discrepancies'][rule] = disc
        elif rule == '4500 == 4450+4400+4490' and cash_items:
            disc = compute_4500_discrepancy(cash_items)
            findings['discrepancies'][rule] = disc
    
    # Additional structural observations
    findings['has_1700'] = has_1700
    findings['has_1300_1400_1500'] = has_1300_1400_1500
    
    # Find escalation artifacts
    pdf_esc_files, tstruct_files = find_esc_artifacts(doc_name)
    findings['pdf_esc_files'] = [os.path.basename(f) for f in pdf_esc_files]
    findings['tstruct_files'] = [os.path.basename(f) for f in tstruct_files]
    
    # Read escalation artifacts and determine verdict
    esc_verdicts = []
    for f in pdf_esc_files:
        data_esc = read_esc_verdict(f)
        if isinstance(data_esc, dict):
            # Compare with original items
            esc_items = data_esc.get('items', [])
            esc_m = val_map_from_items(esc_items)
            orig_m = val_map_from_items(balance_items) if 'balance' in f else val_map_from_items(income_items)
            
            # Check if escalation confirmed or contradicted original
            confirmed = 0
            contradicted = 0
            for code, vals in orig_m.items():
                if code in esc_m:
                    esc_vals = esc_m[code]
                    for i in range(min(len(vals), len(esc_vals))):
                        if vals[i] is not None and esc_vals[i] is not None:
                            if vals[i] == esc_vals[i]:
                                confirmed += 1
                            else:
                                contradicted += 1
            esc_verdicts.append({
                'file': os.path.basename(f),
                'confirmed': confirmed,
                'contradicted': contradicted,
                'items_count': len(esc_items),
            })
    findings['escalation_verdicts'] = esc_verdicts
    
    # Check warnings for escalation verdict text
    for w in findings['warnings']:
        if 'second model agrees; document may not reconcile' in w:
            findings['escalation_verdict'] = 'document internally inconsistent (second model agrees)'
        elif 'unresolved' in w:
            findings['escalation_verdict'] = 'unresolved (escalation could not fix)'
        elif 'fixed by escalation' in w:
            findings['escalation_verdict'] = 'fixed by escalation'
    
    return findings

def check_escalation_corrections(balance_items):
    """Check if escalation corrected values to wrong values by looking at values_ocr1."""
    corrections = []
    for it in balance_items:
        if 'values_ocr1' in it and 'corrected_by' in it:
            corrections.append({
                'code': it.get('code'),
                'name': it.get('name'),
                'original': it['values_ocr1'],
                'corrected': it.get('values'),
            })
        for ch in it.get('children', []):
            if 'values_ocr1' in ch and 'corrected_by' in ch:
                corrections.append({
                    'code': ch.get('code'),
                    'name': ch.get('name'),
                    'original': ch['values_ocr1'],
                    'corrected': ch.get('values'),
                })
    return corrections

def compute_original_check(data, rule):
    """Compute what a check would look like with original (pre-escalation) values."""
    balance = data.get('balance') or {}
    items = balance.get('items', [])
    # Build original val_map using raw_values for corrected items, values for others
    m = {}
    for it in items:
        code = it.get('code')
        if code:
            if 'values_ocr1' in it:
                m[code] = it['values_ocr1']
            else:
                m[code] = it.get('values', [])
    
    if rule == '1200 == 1210+1220+1230+1240+1250+1260':
        codes = ['1210', '1220', '1230', '1240', '1250', '1260']
        vals = m.get('1200', [])
        n = len(vals)
        for c in range(n):
            actual = vals[c] if c < len(vals) else None
            exp_sum = sum((m.get(code, [])[c] if c < len(m.get(code, [])) else None) or 0 for code in codes)
            if actual is not None:
                return actual, exp_sum, actual - exp_sum
    elif rule == '1100 == 1110+1150+1160+1170+1180+1190':
        codes = ['1110', '1150', '1160', '1170', '1180', '1190']
        vals = m.get('1100', [])
        n = len(vals)
        for c in range(n):
            actual = vals[c] if c < len(vals) else None
            exp_sum = sum((m.get(code, [])[c] if c < len(m.get(code, [])) else None) or 0 for code in codes)
            if actual is not None:
                return actual, exp_sum, actual - exp_sum
    elif rule == '1600 == 1700':
        v1600 = m.get('1600', [])
        v1700 = m.get('1700', [])
        n = max(len(v1600), len(v1700))
        for c in range(n):
            a = v1600[c] if c < len(v1600) else None
            b = v1700[c] if c < len(v1700) else None
            if a is not None and b is not None:
                return a, b, a - b
    elif rule == '1300+1400+1500 == 1700':
        v1700 = m.get('1700', [])
        n = len(v1700)
        for c in range(n):
            left = sum((m.get(code, [])[c] if c < len(m.get(code, [])) else None) or 0 for code in ['1300', '1400', '1500'])
            right = v1700[c] if c < len(v1700) else None
            if right is not None:
                return left, right, left - right
    return None, None, None

def classify_cause(finding):
    """Classify the root cause into one of a-e."""
    name = finding['name']
    warnings = finding['warnings']
    failed = finding['failed_checks']
    esc_verdict = finding['escalation_verdict']
    has_1700 = finding.get('has_1700', True)
    has_1300_1400_1500 = finding.get('has_1300_1400_1500', True)
    discrepancies = finding['discrepancies']
    
    # Load full data for deeper analysis
    data = load_json(os.path.join(OUTDIR, name + '.json'))
    balance_data = data.get('balance') or {}
    income_data = data.get('income_statement') or {}
    cash_data = data.get('cash_flow') or {}
    
    structured_by = balance_data.get('structured_by', '') if balance_data else ''
    transcript_pages = balance_data.get('transcript_pages', []) if balance_data else []
    balance_items = balance_data.get('items', [])
    n_items = len(balance_items)
    
    # Check for escalation corrections that made things worse
    corrections = check_escalation_corrections(balance_items)
    
    # === CLASSIFICATION LOGIC ===
    
    # (b) Page-detection error: passive side of balance missing
    # If balance only has active side items (1100-1200/1600) but no passive side (1300+, 1700)
    balance_codes = set()
    for it in balance_items:
        code = it.get('code')
        if code:
            balance_codes.add(code)
    
    has_passive_codes = bool(balance_codes & {'1310', '1320', '1340', '1350', '1360', '1370', '1410', '1420', '1430', '1440', '1450', '1510', '1520', '1530', '1540', '1550'})
    has_1600 = '1600' in balance_codes
    has_1700_in_codes = '1700' in balance_codes
    
    # Check if balance is truncated (only active side)
    if has_1600 and not has_1700_in_codes and not has_passive_codes:
        # Balance has 1600 (active total) but no passive side codes
        # Check if any failed check involves 1700 or passive-side codes
        passive_related = any('1700' in c['rule'] or '1300' in c['rule'] for c in failed)
        if passive_related:
            # Some checks fail because passive side is missing
            # But there might also be 1200 failures
            non_passive_failures = [c for c in failed if '1700' not in c['rule'] and '1300' not in c['rule']]
            if not non_passive_failures:
                return 'b', 'high', f'balance passive side (1300+, 1700) not captured; transcript_pages={transcript_pages}'
            else:
                # Mixed: passive missing AND other failures
                # The passive missing is the dominant issue
                return 'b', 'high', f'balance passive side (1300+, 1700) not captured (primary), plus other check failures; transcript_pages={transcript_pages}'
    
    # Check if balance is severely truncated (only a few items)
    if n_items <= 6 and not has_1700_in_codes and not has_passive_codes:
        return 'b', 'high', f'balance severely truncated ({n_items} items), missing most codes; transcript_pages={transcript_pages}'
    
    # (c) Pipeline bug: escalation corrected values to wrong values
    if corrections:
        # Check if ANY correction made a failing check worse
        for chk in failed:
            rule = chk['rule']
            orig_actual, orig_expected, orig_diff = compute_original_check(data, rule)
            if orig_diff is not None and abs(orig_diff) <= 2:
                # Original would have passed (within tolerance)
                # Check if current check fails
                curr_disc = discrepancies.get(rule, [])
                if curr_disc and any(d[2] is not None and abs(d[2]) > 2 for d in curr_disc):
                    curr_worst = max((abs(d[2]) for d in curr_disc if d[2] is not None), default=0)
                    return 'c', 'high', f'escalation "correction" broke passing check {rule}: original diff={orig_diff:+} (OK) vs post-correction worst={curr_worst:,}; escalation values appear wrong'
        
        # Also check if escalation dramatically worsened a failing check
        for chk in failed:
            rule = chk['rule']
            orig_actual, orig_expected, orig_diff = compute_original_check(data, rule)
            if orig_diff is not None:
                curr_disc = discrepancies.get(rule, [])
                if curr_disc:
                    curr_worst = max((abs(d[2]) for d in curr_disc if d[2] is not None), default=0)
                    if abs(orig_diff) < curr_worst / 10 and curr_worst > 1000:
                        return 'c', 'high', f'escalation "correction" dramatically worsened {rule}: original diff={orig_diff:+,} vs post-correction worst={curr_worst:,}; escalation values appear to be from wrong document'
    
    # (d) Document internally inconsistent
    if esc_verdict and 'document internally inconsistent' in esc_verdict:
        # Check if escalation confirmed all values (no contradictions)
        esc_verdicts = finding.get('escalation_verdicts', [])
        total_contradicted = sum(ev.get('contradicted', 0) for ev in esc_verdicts)
        total_confirmed = sum(ev.get('confirmed', 0) for ev in esc_verdicts)
        
        if total_contradicted == 0 and total_confirmed > 0:
            return 'd', 'high', f'escalation confirmed {total_confirmed} values, contradicted 0; document is internally inconsistent'
        elif total_contradicted > 0:
            # Escalation contradicted some values - might be OCR error
            # But if escalation still agrees on the failing check codes, it's still document inconsistency
            return 'd', 'medium', f'escalation confirmed {total_confirmed}, contradicted {total_contradicted}; document likely inconsistent but some OCR uncertainty'
    
    if esc_verdict and 'unresolved' in esc_verdict:
        return 'd', 'medium', 'escalation unresolved; document likely internally inconsistent'
    
    # (a) OCR/transcription error: escalation contradicted many values
    esc_verdicts = finding.get('escalation_verdicts', [])
    total_contradicted = sum(ev.get('contradicted', 0) for ev in esc_verdicts)
    total_confirmed = sum(ev.get('confirmed', 0) for ev in esc_verdicts)
    if total_contradicted > total_confirmed and total_contradicted > 10:
        return 'a', 'medium', f'escalation contradicted {total_contradicted} values vs {total_confirmed} confirmed; likely OCR error'
    
    # If no escalation artifact exists
    if not finding['pdf_esc_files']:
        return 'e', 'low', 'no escalation artifacts found'
    
    return 'e', 'low', 'unable to determine cause from available data'

def main():
    all_findings = []
    cause_counts = defaultdict(int)
    
    print("=" * 120)
    print("REVIEW TAXONOMY REPORT: needs_review documents")
    print("=" * 120)
    print()
    
    for doc_name in NEEDS_REVIEW:
        finding = analyze_document(doc_name)
        cause, confidence, rationale = classify_cause(finding)
        finding['cause'] = cause
        finding['confidence'] = confidence
        finding['rationale'] = rationale
        all_findings.append(finding)
        cause_counts[cause] += 1
    
    # Print detailed analysis for each document
    for f in all_findings:
        print(f"--- {f['name']} ---")
        print(f"  Status: {f['status']}")
        print(f"  Failed checks:")
        for chk in f['failed_checks']:
            rule = chk['rule']
            form = chk['form']
            per_col = chk['per_column']
            disc = f['discrepancies'].get(rule, [])
            disc_str = ""
            if disc:
                parts = []
                for i, d in enumerate(disc):
                    if d[2] is not None and d[2] != 0:
                        parts.append(f"col{i}: actual={d[0]:,} expected={d[1]:,} diff={d[2]:+,} ({d[3]:.1%})" if d[3] is not None else f"col{i}: actual={d[0]} expected={d[1]} diff={d[2]}")
                    elif d[2] is not None:
                        parts.append(f"col{i}: OK (diff=0)")
                    else:
                        parts.append(f"col{i}: null (one side missing)")
                disc_str = "; ".join(parts)
            print(f"    [{form}] {rule}  per_column={per_col}")
            if disc_str:
                print(f"      Discrepancy: {disc_str}")
        print(f"  Escalation artifacts: {f['pdf_esc_files']}")
        if f['escalation_verdicts']:
            for ev in f['escalation_verdicts']:
                print(f"    {ev['file']}: confirmed={ev['confirmed']} contradicted={ev['contradicted']}")
        print(f"  Escalation verdict: {f['escalation_verdict']}")
        print(f"  Warnings: {f['warnings']}")
        print(f"  Classification: cause={f['cause']}  confidence={f['confidence']}")
        print(f"  Rationale: {f['rationale']}")
        if f.get('has_1700') is not None:
            print(f"  Structural: has_1700={f['has_1700']}  has_1300_1400_1500={f['has_1300_1400_1500']}")
        print()
    
    # Print summary table
    print("=" * 120)
    print("SUMMARY TABLE")
    print("=" * 120)
    print()
    
    # Table header
    hdr = f"{'Документ':<35} {'Форма':<18} {'Упавшая проверка':<42} {'Расхождение':<55} {'Вердикт эскал.':<42} {'Причина':<8} {'Уверенность'}"
    print(hdr)
    print("-" * 180)
    
    for f in all_findings:
        doc = f['name']
        for chk in f['failed_checks']:
            form = chk['form']
            rule = chk['rule']
            per_col = chk['per_column']
            
            # Format discrepancy with actual/expected
            disc = f['discrepancies'].get(rule, [])
            disc_parts = []
            for i, d in enumerate(disc):
                if d[2] is not None and d[2] != 0:
                    disc_parts.append(f"col{i}: {d[0]:,} vs {d[1]:,} diff={d[2]:+,} ({d[3]:.1%})" if d[3] is not None else f"col{i}: actual={d[0]} expected={d[1]} diff={d[2]:+}")
                elif d[2] is not None:
                    disc_parts.append(f"col{i}: OK")
                else:
                    disc_parts.append(f"col{i}: null")
            disc_str = "; ".join(disc_parts) if disc_parts else "N/A"
            
            # Format form name
            form_name = {'balance': '0710001 Баланс', 'income_statement': '0710002 ОФР', 'cash_flow': '0710005 ОДДС'}.get(form, form)
            
            esc_v = f['escalation_verdict'] or 'none'
            cause = f['cause']
            conf = f['confidence']
            
            print(f"{doc:<35} {form_name:<18} {rule:<42} {disc_str:<50} {esc_v:<45} {cause:<8} {conf}")
    
    # Print cause counts
    print()
    print("=" * 120)
    print("CAUSE COUNTS")
    print("=" * 120)
    cause_names = {
        'a': 'OCR/transcription error',
        'b': 'page-detection error',
        'c': 'pipeline/parser bug',
        'd': 'document internally inconsistent',
        'e': 'unresolved/unknown',
    }
    for cause in ['a', 'b', 'c', 'd', 'e']:
        count = cause_counts.get(cause, 0)
        print(f"  ({cause}) {cause_names[cause]}: {count}")
    
    # Count documents where escalation concluded internal inconsistency
    d_count = sum(1 for f in all_findings if f['cause'] == 'd')
    print()
    print(f"Documents where escalation concluded 'document internally inconsistent' (cause d): {d_count} out of 11")
    
    # List them
    for f in all_findings:
        if f['cause'] == 'd':
            print(f"  - {f['name']}: {f['rationale']}")

if __name__ == '__main__':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    main()
