# -*- coding: utf-8 -*-
"""Do the page TRANSCRIPTS contain the passive side (1300..1700) that the final JSON lost?"""
import os, re, glob, json

PAGES = r'D:\models\extracted\pages'
CODES = ['1300', '1310', '1360', '1370', '1400', '1410', '1450', '1500', '1510', '1520',
         '1550', '1600', '1700']
DOCS = ['Эфферон_6мес_2025', 'КИФА_6мес_2026', 'Проект 111_6мес_2026', 'Проект 111_6мес_2025']

for doc in DOCS:
    print(f'\n########## {doc} ##########')
    files = sorted(glob.glob(os.path.join(PAGES, f'{doc}*')))
    # only transcription transcripts (md), plus struct caches (json)
    for f in files:
        b = os.path.basename(f)
        if not (b.endswith('.md') or b.endswith('.json')):
            continue
        if not b.startswith(doc):
            continue
        txt = open(f, encoding='utf-8', errors='replace').read()
        found = [c for c in CODES if re.search(r'(?<!\d)' + c + r'(?!\d)', txt)]
        print(f'  {b[:62]:62} {len(txt):7}B  codes_found={found}')

# where are the balance pages for these docs according to the final JSON?
print('\n########## source.pages_used in final JSON ##########')
for doc in DOCS:
    p = os.path.join(r'D:\models\extracted', doc + '.json')
    j = json.load(open(p, encoding='utf-8'))
    print(f'  {doc:26} pages_total={j["source"].get("pages_total")} pages_used={j["source"].get("pages_used")} '
          f'text_layer={j["source"].get("text_layer")}')
    for form in ('balance', 'income_statement', 'cash_flow'):
        f = j.get(form) or {}
        print(f'      {form:17} pages={f.get("pages")} items={len(f.get("items") or [])}')
