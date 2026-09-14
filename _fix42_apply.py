# -*- coding: utf-8 -*-
"""Live verification of the 4.2 fix on ONE document.
Backs up the JSON, runs process(), compares before/after, checks the свод is untouched.
Usage: python _fix42_apply.py "КИФА_6мес_2026"
"""
import os, sys, io, json, shutil, hashlib, time
sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
DL = r'D:\data-scraping\downloads'
BACKUP = os.path.join(EX, '_backup_4_2')
os.makedirs(BACKUP, exist_ok=True)

name = sys.argv[1] if len(sys.argv) > 1 else 'КИФА_6мес_2026'
stem = os.path.splitext(name)[0]
jp = os.path.join(EX, stem + '.json')

svod = os.path.join(EX, 'svod_2025_2026.csv')
def svod_hash():
    h = hashlib.sha1()
    with open(svod, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()[:12].upper()

before_svod = svod_hash()
print(f'свод до правки: sha1 {before_svod}')

if os.path.exists(jp):
    shutil.copy2(jp, os.path.join(BACKUP, stem + '.json'))
    print(f'бэкап: {os.path.join(BACKUP, stem + ".json")}')
    old = json.load(io.open(jp, encoding='utf-8'))
else:
    old = None
    print('старого JSON нет')


def snapshot(j):
    if not j:
        return {}
    out = {}
    for form in ('balance', 'income_statement', 'cash_flow'):
        f = j.get(form)
        if not f:
            out[form] = None
            continue
        out[form] = {'codes': sorted(P.codes_deep(f.get('items'))),
                     'rows': len(f.get('items') or []),
                     'pages': f.get('transcript_pages'),
                     'by': f.get('structured_by'),
                     'complete': P.form_is_complete(form, f.get('items'))}
    return out

snap_old = snapshot(old)
usage_before = dict(P.USAGE) if hasattr(P, 'USAGE') else {}

t0 = time.time()
res = P.process(os.path.join(DL, name + '.pdf'))
dt = time.time() - t0

snap_new = snapshot(res)
print(f'\n=== ДО -> ПОСЛЕ ({dt:.0f} с) ===')
for form in ('balance', 'income_statement', 'cash_flow'):
    a, b = snap_old.get(form), snap_new.get(form)
    if a == b:
        print(f'  {form:17} без изменений')
        continue
    print(f'  {form:17}')
    for k in ('rows', 'complete', 'by', 'pages'):
        if (a or {}).get(k) != (b or {}).get(k):
            print(f'      {k:9} {a and a.get(k)}  ->  {b and b.get(k)}')
    ca, cb = set((a or {}).get('codes') or []), set((b or {}).get('codes') or [])
    if cb - ca:
        print(f'      +коды    {sorted(cb - ca)}')
    if ca - cb:
        print(f'      -коды    {sorted(ca - cb)}')

print(f'\nstatus: {res.get("status")}')
print('предупреждения 4.2:')
for w in res.get('warnings') or []:
    if 'cut off' in w or 'did not yield' in w or 'recovering' in w or 'kept rule parse' in w:
        print('   ', w)
print('\nпроверки баланса:')
for c in res.get('checks') or []:
    if c['form'] == 'balance':
        print(f'    {c["rule"]:45} {c["per_column"]} ok={c["ok"]}')

after_svod = svod_hash()
print(f'\nсвод после: sha1 {after_svod}  '
      f'{"НЕ ИЗМЕНЁН" if after_svod == before_svod else "!!! ИЗМЕНИЛСЯ !!!"}')
if hasattr(P, 'USAGE'):
    print(f'usage: {P.USAGE}')
