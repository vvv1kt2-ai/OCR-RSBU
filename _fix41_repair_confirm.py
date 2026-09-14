# -*- coding: utf-8 -*-
"""Post-fix repair: the foreign-document sweep also dropped two `confirmed_by` marks that
were legitimate — ТГК-14_6мес_2026's income statement was re-read from ТГК-14's OWN page
(x_p4), not from Корпсан's. Restore them from the backup.

Run with --apply to write.
"""
import os, json, sys

EX = r'D:\models\extracted'
BACKUP = os.path.join(EX, '_backup_4_1')
APPLY = '--apply' in sys.argv

fn = 'ТГК-14_6мес_2026.json'
old = json.load(open(os.path.join(BACKUP, fn), encoding='utf-8'))
new = json.load(open(os.path.join(EX, fn), encoding='utf-8'))

print('company block:', json.dumps(new.get('company'), ensure_ascii=False))

old_is = {i.get('code'): i for i in (old.get('income_statement') or {}).get('items') or []}
new_is = {i.get('code'): i for i in (new.get('income_statement') or {}).get('items') or []}
restored = 0
for code, rec in new_is.items():
    o = old_is.get(code)
    if not o:
        continue
    if o.get('confirmed_by') and not rec.get('confirmed_by') and o.get('values') == rec.get('values'):
        rec['confirmed_by'] = o['confirmed_by']
        restored += 1
        print('  restore confirmed_by=%s on income_statement code %s (values=%s)'
              % (o['confirmed_by'], code, rec.get('values')))
print('restored marks:', restored)

if APPLY and restored:
    json.dump(new, open(os.path.join(EX, fn), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('written')
elif not APPLY:
    print('DRY RUN — re-run with --apply')
