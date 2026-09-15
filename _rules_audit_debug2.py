# -*- coding: utf-8 -*-
"""Debug: find ALL docs where 1200 rule fails, and check 1215."""
import sys, json
from pathlib import Path

sys.path.insert(0, 'D:/models')
sys.path.insert(0, 'D:/models/pylibs')
import pipeline

EXTRACTED = Path('D:/models/extracted')
files = sorted(f for f in EXTRACTED.glob('*.json') if not f.name.startswith('_'))

print("=== Balance: 1200 rule failures ===\n")
for fpath in files:
    doc_name = fpath.stem
    data = json.loads(fpath.read_text(encoding='utf-8'))
    bal = data.get('balance')
    if not bal:
        continue
    items = bal['items']

    checks = pipeline.run_checks('balance', items)
    for chk in checks:
        if '1200' in chk['rule'] and not chk['ok']:
            # Find 12xx codes
            m = {}
            for it in items:
                c = it.get('code')
                if c and c.startswith('12'):
                    m[c] = it.get('values')
            has_1215 = any(it.get('code') == '1215' for it in items)
            print(f"{doc_name}: FAIL  per_col={chk['per_column']}")
            print(f"  12xx codes: {sorted(m.keys())}")
            if has_1215:
                print(f"  1215 values: {m.get('1215')}")
            else:
                print(f"  1215 NOT in items")
            # Show the raw 1200 and sum
            v1200 = m.get('1200')
            sum_rhs = [m.get('1210'), m.get('1220'), m.get('1230'), m.get('1240'), m.get('1250'), m.get('1260')]
            print(f"  1200 values: {v1200}")
            print(f"  RHS codes present: {[k for k in ('1210','1220','1230','1240','1250','1260') if k in m]}")
            print()

print("\n=== All balance checks summary ===\n")
n_pass = 0
n_fail = 0
for fpath in files:
    doc_name = fpath.stem
    data = json.loads(fpath.read_text(encoding='utf-8'))
    bal = data.get('balance')
    if not bal:
        continue
    items = bal['items']
    checks = pipeline.run_checks('balance', items)
    for chk in checks:
        if '1200' in chk['rule']:
            if chk['ok']:
                n_pass += 1
            else:
                n_fail += 1
print(f"1200 rule: {n_pass} pass, {n_fail} fail")
