# -*- coding: utf-8 -*-
r"""Какие коды с ЗАПОЛНЕННЫМИ значениями не покрыты ни одним правилом формы.

Проверяет не «правильно ли правило написано», а «есть ли в данных код, которого
нет в правилах»: именно такой код даёт ложный провал и ложную эскалацию.
Аудит подагента утверждал, что у правила 1100 изъянов нет; проверяю по данным.
"""
import io, os, json, sys, re

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
FORMS = ('balance', 'income_statement', 'cash_flow')

# коды-родители, которые сами являются итогами правил (не требуют покрытия)
KNOWN_TOTAL = {'1600', '1700', '1100', '1200', '1300', '1400', '1500',
               '2100', '2200', '2300', '2400', '2500',
               '4100', '4200', '4300', '4400', '4450', '4490', '4500'}


def has_val(it):
    return any(v not in (None, '', '-') for v in (it.get('values') or []))


def codes_in_rule(rule):
    return set(re.findall(r'\d{4}', rule or ''))


rows = {}
for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    for form in FORMS:
        fd = doc.get(form) or {}
        items = fd.get('items') or []
        if not items:
            continue
        checks = P.run_checks(form, items)
        covered = set()
        for c in checks:
            covered |= codes_in_rule(c.get('rule'))
        filled = {str(it.get('code') or ''): has_val(it) for it in items}
        filled = {k: v for k, v in filled.items() if re.fullmatch(r'\d{4}', k) and v}
        gap = sorted(k for k in filled if k not in covered and k not in KNOWN_TOTAL)
        if gap:
            rows.setdefault((form, tuple(gap)), []).append(stem)

print('=== коды с заполненными значениями, не покрытые правилами ===')
if not rows:
    print('нет')
for (form, gap), stems in sorted(rows.items(), key=lambda x: -len(x[1])):
    print('%-18s коды %-22s документов %d' % (form, ','.join(gap), len(stems)))
    print('   %s' % ', '.join(s[:34] for s in stems[:5]))
print()

# прицельно: подкоды правила 1100 и правила 1200
print('=== подкоды 1100 и 1200 в данных (заполнено / всего документов) ===')
for form, codes in (('balance', ('1105', '1120', '1130', '1140', '1215')),):
    stat = {c: [0, 0] for c in codes}
    for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
        doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
        fd = doc.get(form) or {}
        items = fd.get('items') or []
        if not items:
            continue
        for c in codes:
            if any(str(it.get('code') or '') == c for it in items):
                stat[c][1] += 1
                if any(str(it.get('code') or '') == c and has_val(it) for it in items):
                    stat[c][0] += 1
    for c in codes:
        print('  %s: заполнено %d из %d' % (c, stat[c][0], stat[c][1]))

json.dump([{'form': f, 'codes': list(g), 'docs': d} for (f, g), d in rows.items()],
          io.open(r'D:\models\_rules_gap.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
