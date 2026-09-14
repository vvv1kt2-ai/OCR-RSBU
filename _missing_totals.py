# -*- coding: utf-8 -*-
"""Find JSONs with missing balance totals / empty forms / non-ok status."""
import json, glob, os

rows = []
for p in sorted(glob.glob(r'D:\models\extracted\*.json')):
    b = os.path.basename(p)
    if b.startswith('_'):
        continue
    d = json.load(open(p, encoding='utf-8'))
    if 'balance' not in d:
        continue
    counts = {}
    for form in ('balance', 'income_statement', 'cash_flow'):
        f = d.get(form) or {}
        counts[form] = (len(f.get('items') or []), len(f.get('columns') or []))
    bal_codes = [i.get('code') for i in (d.get('balance') or {}).get('items') or []]
    need = ['1100', '1200', '1300', '1400', '1500', '1600', '1700']
    miss = [c for c in need if c not in bal_codes]
    if miss or counts['balance'][0] < 12 or d.get('status') != 'ok':
        rows.append((b, d.get('status'), counts, miss))

hdr = f'{"file":50} {"status":14} {"bal":10} {"is":10} {"cf":10} missing_totals'
print(hdr)
for b, st, c, miss in sorted(rows, key=lambda x: -len(x[3])):
    print(f'{b[:50]:50} {str(st):14} {str(c["balance"]):10} {str(c["income_statement"]):10} '
          f'{str(c["cash_flow"]):10} {miss}')
print()
print('files with missing totals or non-ok status:', len(rows), 'of 41')
