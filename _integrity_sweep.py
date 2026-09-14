# -*- coding: utf-8 -*-
"""Final integrity sweep: which escalation artifacts are duplicates, which docs
carry 'confirmed_by' from the same contaminated source, and is the свод affected."""
import os, json, glob, hashlib, collections

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

print('=== A. sha1 of every escalation artifact ===')
by_hash = collections.defaultdict(list)
for f in sorted(glob.glob(os.path.join(PAGES, '*_esc_*.json'))):
    raw = open(f, 'rb').read()
    h = hashlib.sha1(raw).hexdigest()[:10]
    by_hash[h].append(os.path.basename(f))
for h, names in by_hash.items():
    tag = '  <== ДУБЛИКАТ' if len(names) > 1 else ''
    for n in names:
        print(f'  {h}  {n}{tag}')

print('\n=== B. docs carrying confirmed_by / corrected_by from escalation ===')
for f in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(f)
    if b.startswith('_'):
        continue
    d = json.load(open(f, encoding='utf-8'))
    conf = set(); corr = set()
    for form in ('balance', 'income_statement', 'cash_flow'):
        for i in (d.get(form) or {}).get('items') or []:
            if i.get('confirmed_by'): conf.add(i['confirmed_by'])
            if i.get('corrected_by'): corr.add(i['corrected_by'])
    if conf or corr:
        print(f'  {b[:46]:46} confirmed_by={sorted(conf)} corrected_by={sorted(corr)}')

print('\n=== C. свод columns vs codes that were actually corrupted ===')
CORRUPTED = {'Органик парк_6мес_2025': ['1110', '1150', '1180', '1100'],
             'ТГК-14_6мес_2025': ['1210'], 'ТГК-14_6мес_2026': ['1210'],
             'Славянск ЭКО_6мес_2025': ['1100', '1240']}
import csv
rows = list(csv.reader(open(os.path.join(EX, 'svod_2025_2026.csv'), encoding='utf-8-sig'), delimiter=';'))
svod_codes = set()
for h in rows[0][1:]:
    svod_codes.add(h.split('_')[0].split('+')[0])
print('  коды в своде:', sorted(svod_codes))
for doc, codes in CORRUPTED.items():
    overlap = [c for c in codes if c in svod_codes]
    print(f'  {doc:24} повреждённые коды={codes} -> пересечение со сводом: {overlap or "НЕТ"}')
