# -*- coding: utf-8 -*-
"""Defect 4.1 proof, part 2: the contaminated values ARE Корпсан's numbers.

Checks, for each row escalation rewrote:
  1. does the new value equal Корпсан_6мес_2026's own value for the same code?
  2. cross-year consistency: the date 31.12.2024 appears in both the 2025 and the
     2026 file of the same company; the two values must agree. Escalation breaks it.
  3. which document's pages the escalation transcripts actually were.
"""
import os, json, re, glob, datetime

EX = r'D:\models\extracted'
PAGES = r'D:\models\extracted\pages'


def load(p):
    return json.load(open(p, encoding='utf-8'))


def rows(doc, form):
    out = {}
    for it in ((doc.get(form) or {}).get('items') or []):
        for rec in [it] + (it.get('children') or []):
            key = (rec.get('code'), (rec.get('name') or '').strip()[:28])
            out[key] = rec
    return out


korp = load(os.path.join(EX, 'Корпсан_6мес_2026.json'))
krows = rows(korp, 'balance')

print('=== 1. are the rewritten values Корпсан\'s own numbers? ===')
victims = [('Органик парк_6мес_2025.json', 'balance'),
           ('ТГК-14_6мес_2025.json', 'balance'),
           ('ТГК-14_6мес_2026.json', 'balance')]
for fn, form in victims:
    d = load(os.path.join(EX, fn))
    print('\n--- %s' % fn)
    for (code, name), rec in sorted(rows(d, form).items(), key=lambda x: str(x[0][0])):
        v1, v = rec.get('values_ocr1'), rec.get('values')
        if v1 is None or v1 == v:
            continue
        kor = krows.get((code, name)) or krows.get((code, ''))
        kv = kor.get('values') if kor else None
        same = 'IDENTICAL to Корпсан' if kv == v else ('kor=%s' % kv)
        print('    code %-5s %-28s ocr1=%-30s final=%-30s -> %s' % (code, name, v1, v, same))

print('\n=== 2. cross-year consistency on the shared date 31.12.2024 ===')
for comp in ('ТГК-14',):
    a = load(os.path.join(EX, f'{comp}_6мес_2025.json'))
    b = load(os.path.join(EX, f'{comp}_6мес_2026.json'))
    ca, cb = (a['balance'] or {}).get('columns') or [], (b['balance'] or {}).get('columns') or []
    ia = next((i for i, c in enumerate(ca) if '2024' in c), None)
    ib = next((i for i, c in enumerate(cb) if '2024' in c), None)
    print('  columns 2025-file: %s  -> index of 2024 = %s' % (ca, ia))
    print('  columns 2026-file: %s  -> index of 2024 = %s' % (cb, ib))
    ra, rb = rows(a, 'balance'), rows(b, 'balance')
    for key in sorted(set(ra) & set(rb), key=lambda x: str(x[0])):
        x, y = ra[key], rb[key]
        if x.get('values') is None:
            continue
        va, vb = x.get('values') or [], y.get('values') or []
        if ia is None or ib is None or len(va) <= ia or len(vb) <= ib:
            continue
        f = va[ia] == vb[ib]
        oa, ob = x.get('values_ocr1') or va, y.get('values_ocr1') or vb
        g = (oa[ia] if len(oa) > ia else None) == (ob[ib] if len(ob) > ib else None)
        if not f or not g:
            print('  %s %s' % (key[0], key[1][:26]))
            print('     31.12.2024 in 2025-file: final=%-12s ocr1=%-12s' % (va[ia], oa[ia] if len(oa) > ia else None))
            print('     31.12.2024 in 2026-file: final=%-12s ocr1=%-12s' % (vb[ib], ob[ib] if len(ob) > ib else None))
            print('     final %s / ocr1 %s' % ('CONTRADICTION' if not f else 'consistent',
                                               'CONTRADICTION' if not g else 'consistent'))

print('\n=== 3. provenance of the escalation transcripts ===')
for p in sorted(glob.glob(os.path.join(PAGES, 'x_p*'))):
    txt = open(p, encoding='utf-8').read()
    inn = re.search(r'ИНН[:\s]*(\d{10,12})', txt)
    okpo = re.search(r'ОКПО[:\s]*(\d{8,10})', txt)
    org = re.search(r'Организация[:\s]*(.{0,70})', txt)
    st = os.stat(p)
    print('  %-10s %s  ИНН=%s ОКПО=%s' % (
        os.path.basename(p).split('.')[0], datetime.datetime.fromtimestamp(st.st_mtime),
        inn.group(1) if inn else '-', okpo.group(1) if okpo else '-'))
    if org:
        print('      org: %s' % org.group(1).strip())
print('\n  Корпсан company block: ИНН=%s ОКПО=%s' % (
    (korp.get('company') or {}).get('inn'), (korp.get('company') or {}).get('okpo')))
