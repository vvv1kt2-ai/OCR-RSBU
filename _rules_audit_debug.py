# -*- coding: utf-8 -*-
"""Debug: why does adding 1215 not fix the 1200 rule failures?"""
import sys, json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, 'D:/models')
sys.path.insert(0, 'D:/models/pylibs')
import pipeline

EXTRACTED = Path('D:/models/extracted')
files = sorted(f for f in EXTRACTED.glob('*.json') if not f.name.startswith('_'))

# Find docs where 1200 rule fails
for fpath in files[:5]:  # check first 5
    doc_name = fpath.stem
    data = json.loads(fpath.read_text(encoding='utf-8'))
    bal = data.get('balance')
    if not bal:
        continue
    items = bal['items']

    # Run checks
    checks = pipeline.run_checks('balance', items)
    for chk in checks:
        if '1200' in chk['rule'] and not chk['ok']:
            print(f"\n=== {doc_name} ===")
            print(f"Rule: {chk['rule']}, ok={chk['ok']}")
            print(f"Per column: {chk['per_column']}")

            # Find 1200 and all 12xx codes in items
            m = {}
            for it in items:
                c = it.get('code')
                if c and c.startswith('12'):
                    m[c] = it.get('values')
            print(f"12xx codes in doc: {sorted(m.keys())}")
            for code in sorted(m.keys()):
                print(f"  {code}: {m[code]}")

            # Check if 1215 exists
            has_1215 = any(it.get('code') == '1215' for it in items)
            print(f"Has 1215 in items: {has_1215}")

# Also check cash flow gap
print("\n\n=== CASH FLOW GAP CHECK ===")
for fpath in files[:5]:
    doc_name = fpath.stem
    data = json.loads(fpath.read_text(encoding='utf-8'))
    cf = data.get('cash_flow')
    if not cf:
        continue
    items = cf['items']
    codes = {it.get('code') for it in items if it.get('code')}
    cf_codes = sorted(c for c in codes if c.startswith('4'))
    if cf_codes:
        print(f"\n{doc_name}: {cf_codes}")
