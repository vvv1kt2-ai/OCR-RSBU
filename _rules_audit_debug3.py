# -*- coding: utf-8 -*-
"""Debug: what are the cashflow and income/cashflow related codes?"""
import sys, json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, 'D:/models')
sys.path.insert(0, 'D:/models/pylibs')

EXTRACTED = Path('D:/models/extracted')
files = sorted(f for f in EXTRACTED.glob('*.json') if not f.name.startswith('_'))

codes_income = defaultdict(dict)
codes_cashflow = defaultdict(dict)

for fpath in files:
    doc_name = fpath.stem
    try:
        data = json.loads(fpath.read_text(encoding='utf-8'))
    except:
        continue
    for form_key, storage in [('income_statement', codes_income), ('cash_flow', codes_cashflow)]:
        form = data.get(form_key)
        if not form or not form.get('items'):
            continue
        for it in form['items']:
            code = it.get('code')
            vals = it.get('values')
            if code and vals:
                storage[code][doc_name] = vals

print("=== Income codes ===")
for code in sorted(codes_income.keys()):
    n = sum(1 for v in codes_income[code].values() if any(x is not None for x in v))
    print(f"  {code}: {n} docs with value")

print("\n=== Cashflow codes ===")
for code in sorted(codes_cashflow.keys()):
    n = sum(1 for v in codes_cashflow[code].values() if any(x is not None for x in v))
    print(f"  {code}: {n} docs with value")

# Cashflow rules use 4400 as sum_of_children with parent_code=4400
# Check what children 4400 has
print("\n=== Cashflow: children of 4400 ===")
prefix_44 = set()
for code in codes_cashflow:
    if code.startswith('44') and code != '4400':
        prefix_44.add(code)
print(f"  44xx codes (excl 4400): {sorted(prefix_44)}")

# Cashflow rule 4500 == 4450+4400+4490: check children of 4500
print("\n=== Cashflow: children of 4500 ===")
prefix_45 = set()
for code in codes_cashflow:
    if code.startswith('45') and code != '4500':
        prefix_45.add(code)
print(f"  45xx codes (excl 4500): {sorted(prefix_45)}")
