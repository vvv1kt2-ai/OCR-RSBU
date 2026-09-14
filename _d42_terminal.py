# -*- coding: utf-8 -*-
"""Is a terminal-code completeness rule safe? Count, over the 41 result JSONs,
how often the last row of each form is present. Terminal codes:
balance 1700, income 2400, cash_flow 4500 (and 4400 as an alternative tail)."""
import os, io, re, json, glob

OUT = r'D:\models\extracted'
TERM = {'balance': ('1700',), 'income_statement': ('2400',), 'cash_flow': ('4500',)}
ALT = {'cash_flow': ('4400',)}
rows = []
for p in sorted(glob.glob(os.path.join(OUT, '*.json'))):
    b = os.path.basename(p)
    if b.startswith('_'):
        continue
    j = json.load(io.open(p, encoding='utf-8'))
    r = {'doc': b[:-5]}
    for form, terms in TERM.items():
        f = j.get(form)
        if not f:
            r[form] = 'нет формы'
            continue
        cs = set()
        def walk(items):
            for it in items or []:
                cs.add(str(it.get('code')))
                walk(it.get('children'))
        walk(f.get('items'))
        miss = [t for t in terms if t not in cs]
        if not miss:
            r[form] = 'ok'
        elif any(t in cs for t in ALT.get(form, ())):
            r[form] = f'нет {",".join(miss)} (есть альт.)'
        else:
            r[form] = f'НЕТ {",".join(miss)}'
    rows.append(r)

def count(pred):
    return sum(1 for r in rows if pred(r))

print(f'всего JSON: {len(rows)}')
for form in TERM:
    ok = count(lambda r, f=form: r[f] == 'ok')
    nof = count(lambda r, f=form: r[f] == 'нет формы')
    bad = count(lambda r, f=form: r[f].startswith('НЕТ'))
    alt = count(lambda r, f=form: 'альт' in r[f])
    print(f'  {form:17} последняя строка есть: {ok:3}  нет формы: {nof:3}  ОТСУТСТВУЕТ: {bad:3}  (альт. хвост: {alt})')
print('--- где отсутствует ---')
for r in rows:
    bad = [f'{k}={v}' for k, v in r.items() if k != 'doc' and v.startswith('НЕТ')]
    if bad:
        print(f'  {r["doc"][:44]:44} {" ".join(bad)}')
