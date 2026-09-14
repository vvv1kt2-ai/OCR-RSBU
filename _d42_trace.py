# -*- coding: utf-8 -*-
"""Defect 4.2, step 2: WHY is the passive page dropped? Reproduce find_form_pages
decision-by-decision for the four affected documents. Full detail -> _d42_trace.md."""
import os, re, io, sys, json
sys.path.insert(0, r'D:\models')
import pipeline as P
import fitz

DOCS = ['КИФА_6мес_2026', 'Проект 111_6мес_2026', 'Эфферон_6мес_2025', 'Проект 111_6мес_2025']
DL = r'D:\data-scraping\downloads'
CODES = {'balance': '0710001', 'income_statement': '0710002', 'cash_flow': '0710005'}
TITLES = {'balance': ['Бухгалтерский баланс'],
          'income_statement': ['Отчет о финансовых результатах', 'Отчёт о финансовых результатах'],
          'cash_flow': ['Отчет о движении денежных средств', 'Отчёт о движении денежных средств']}
SKIP = ['Отчет об изменениях капитала', 'Отчёт об изменениях капитала',
        'Пояснения к бухгалтерскому', 'Отчет о целевом использовании']
BAL_CODES = {'1100', '1110', '1150', '1160', '1170', '1180', '1190', '1200',
             '1210', '1220', '1230', '1240', '1250', '1260', '1300', '1310',
             '1360', '1370', '1400', '1410', '1420', '1430', '1450', '1500',
             '1510', '1520', '1530', '1540', '1550', '1600', '1700'}
BAL_ORDER = ['1100', '1110', '1150', '1170', '1180', '1190', '1200', '1210', '1230',
             '1240', '1250', '1260', '1600', '1300', '1310', '1360', '1370', '1400',
             '1410', '1450', '1500', '1510', '1520', '1550', '1700']

out = io.open(r'D:\models\_d42_trace.md', 'w', encoding='utf-8')


def w(s=''):
    out.write(s + '\n')


for name in DOCS:
    pdf = os.path.join(DL, name + '.pdf')
    if not os.path.exists(pdf):
        print('MISSING PDF', name)
        continue
    doc = fitz.open(pdf)
    pages = P.find_form_pages(doc)
    w(f'\n# {name}  ({len(doc)} pages)')
    w(f'\nfind_form_pages -> ' + json.dumps(pages, ensure_ascii=False))

    bal = pages.get('balance') or []
    # per-page trace around the balance region
    lo = max(1, (bal[0] if bal else 1))
    hi = min(len(doc), (bal[-1] if bal else 1) + 3)
    w(f'\n## Трассировка страниц {lo}..{hi} (баланс: {bal})')
    for p in range(lo, hi + 1):
        t = doc[p - 1].get_text()
        codes = sorted(BAL_CODES & set(re.findall(r'\d{4}', t)))
        hits = len(codes)
        lines = [x.strip() for x in t.splitlines() if x.strip()]
        nval = sum(1 for x in lines if P.is_value_line(x) or P.CODE_RE.match(x))
        nprose = sum(1 for x in lines if len(x) > 70)
        sig = [x[:30] for x in lines if re.match(r'(Директор|Главный бухгалтер|Руководитель)\b', x)]
        skiphit = [m for m in SKIP if m in t]
        otherhit = [k for k in CODES if k != 'balance'
                    and (CODES[k] in t or any(ti in t for ti in TITLES[k]))]
        own = ('0710001' in t) or any(ti in t for ti in TITLES['balance'])
        w(f'\n### стр. {p}  len={len(t)}  bal_codes={hits} {codes}')
        w(f'  own_marker={own} other_form={otherhit} SKIP={skiphit} nval={nval} nprose={nprose} sig={sig}')
        w(f'  -> verdict: ' + (
            'STOP: SKIP' if (skiphit and '0710001' not in t and hits < 3) else
            'KEEP: own marker/codes' if (own or hits >= 3) else
            'STOP: other form' if otherhit else
            'STOP: signature' if sig else
            'KEEP: table content' if (nval >= 6 and nprose <= 2) else 'miss'))
        # first 25 lines of the page, so the shape is visible
        for x in lines[:25]:
            w('    | ' + x[:100])
    doc.close()

out.close()

# terminal summary: which pages hold 1600/1700, which pages were used
print(f'{"документ":26} {"страниц":>7} {"balance pages":>16}  pages with 1600 / 1700')
for name in DOCS:
    pdf = os.path.join(DL, name + '.pdf')
    if not os.path.exists(pdf):
        continue
    doc = fitz.open(pdf)
    pgs = P.find_form_pages(doc)
    p16 = [i + 1 for i, pg in enumerate(doc) if re.search(r'(?<!\d)1600(?!\d)', pg.get_text())]
    p17 = [i + 1 for i, pg in enumerate(doc) if re.search(r'(?<!\d)1700(?!\d)', pg.get_text())]
    print(f'{name:26} {len(doc):>7} {str(pgs.get("balance")):>16}  {p16} / {p17}')
    doc.close()
