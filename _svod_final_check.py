# -*- coding: utf-8 -*-
"""Do contaminated docs carry Корпсан's values in the codes the свод actually uses?"""
import os, json, csv

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

def load(p):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return {}

SVOD_CODES = ['1250', '1300', '1410', '1450', '1510', '1550', '2110', '2300', '2330', '2320', '4100', '4110']

korpsan = load(os.path.join(PAGES, '_llm_Корпсан_6мес_2026.pdf_esc_balance.json'))
kor = {i['code']: i.get('values') for i in korpsan.get('items') or [] if i.get('code')}
print('Корпсан esc balance codes:', sorted(kor))

for doc in ['Органик парк_6мес_2025', 'ТГК-14_6мес_2025', 'ТГК-14_6мес_2026', 'Славянск ЭКО_6мес_2025']:
    d = load(os.path.join(EX, doc + '.json'))
    bal = {i['code']: i for i in (d.get('balance') or {}).get('items') or [] if i.get('code')}
    print(f'\n--- {doc} ---')
    for c in SVOD_CODES:
        it = bal.get(c)
        if not it:
            continue
        fin = it.get('values'); ocr1 = it.get('values_ocr1')
        k = kor.get(c)
        same_as_korpsan = (fin == k) if (fin and k) else None
        print(f'  {c}: final={fin}  ocr1={ocr1}  корпсан={k}  identical_to_корпсан={same_as_korpsan} '
              f'corrected_by={it.get("corrected_by")}')

print('\n\n=== свод: значения этих эмитентов по этим кодам ===')
rows = list(csv.reader(open(os.path.join(EX, 'svod_2025_2026.csv'), encoding='utf-8-sig'), delimiter=';'))
hdr = [h.strip() for h in rows[0]]
idx = {h: i for i, h in enumerate(hdr)}
for name in ['Органик парк', 'ТГК-14', 'Корпсан', 'Славянск ЭКО']:
    for r in rows[1:]:
        if r and r[0].strip() == name:
            vals = {h: r[idx[h]] for h in hdr if h != 'эмитент' and h.split('_')[0] in SVOD_CODES}
            print(f'  {name:14} {vals}')
            break
    else:
        print(f'  {name:14} НЕТ В СВОДЕ')
