# -*- coding: utf-8 -*-
"""Defect 4.3, step 1 (free, no LLM): inventory of duplicate codes and lease rows
in the 41 balance JSONs, and what the свод does with them.
Report -> _d43_inventory.md
"""
import os, sys, io, json, glob, re
sys.path.insert(0, r'D:\models')
sys.path.insert(0, r'D:\models\pylibs')
import svod

EX = r'D:\models\extracted'
out = io.open(r'D:\models\_d43_inventory.md', 'w', encoding='utf-8')
w = out.write
w('# Дефект 4.3 — инвентаризация дублей кодов и аренды\n\n')

docs = []
for p in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(p)
    if b.startswith('_'):
        continue
    j = json.load(io.open(p, encoding='utf-8'))
    bal = j.get('balance')
    if not bal:
        continue
    svod.mark_chains(bal)
    items_all = list(svod.walk(bal.get('items') or []))
    top = bal.get('items') or []

    occ = {}
    for it in items_all:
        c = it.get('code')
        if c:
            occ.setdefault(c, []).append(it)
    dups = {c: v for c, v in occ.items() if len(v) > 1}

    lease = []
    for it in items_all:
        nm = it.get('name') or ''
        if svod.LEASE_RE.search(nm) or svod.LONG_RENT_RE.search(nm) or svod.SHORT_RENT_RE.search(nm):
            lease.append(it)

    idx = svod.col_index_balance(bal, 2026) if '2026' in b else svod.col_index_balance(bal, 2025)
    long_v, short_v, notes, susp = (None, None, [], False)
    if idx is not None:
        long_v, short_v, notes, susp = svod.rent_extract(bal, idx)

    def v_of(it):
        v = it.get('values') or []
        return v[idx] if (idx is not None and idx < len(v)) else None

    def top_of(code):
        """последний ВЕРХНЕУРОВНЕВЫЙ item с этим кодом — ровно то, что берёт get_val"""
        lst = [it for it in top if it.get('code') == code]
        return lst[-1] if lst else None

    docs.append({'doc': b[:-5], 'idx': idx, 'dups': dups, 'lease': lease,
                 'long': long_v, 'short': short_v, 'susp': susp, 'notes': notes,
                 'top1520': [it for it in top if it.get('code') == '1520'],
                 'top1550': [it for it in top if it.get('code') == '1550'],
                 'v_of': v_of, 'cols': bal.get('columns'),
                 'base1550': v_of(top_of('1550')) if top_of('1550') else None,
                 'base1450': v_of(top_of('1450')) if top_of('1450') else None})

# --- 1. сводка по дублям ---
with_dups = [d for d in docs if d['dups']]
print(f'балансов: {len(docs)}; с дублями кодов: {len(with_dups)}')
w('## 1. Сводка\n\n')
w(f'- балансов разобрано: {len(docs)}\n- с дублями кодов (любой уровень): **{len(with_dups)}**\n')
code_count = {}
for d in docs:
    for c in d['dups']:
        code_count[c] = code_count.get(c, 0) + 1
w('\n| код | в скольких документах дублируется |\n|---|---|\n')
for c, n in sorted(code_count.items(), key=lambda x: -x[1]):
    w(f'| {c} | {n} |\n')

# --- 2. дубли на ВЕРХНЕМ уровне (их и видит get_val) ---
w('\n## 2. Дубли на верхнем уровне — то, что решает get_val\n\n')
w('`get_val` берёт ПОСЛЕДНИЙ верхнеуровневый item с кодом.\n\n')
w('| документ | код | имена верхнеуровневых строк (в порядке следования) | значения |\n|---|---|---|---|\n')
n_top = 0
for d in docs:
    # все верхнеуровневые дубли, не только 1520/1550
    for c, lst in sorted(d['dups'].items()):
        tl = [it for it in lst if not (it.get('_chain') or [])]
        if len(tl) > 1:
            n_top += 1
            names = ' | '.join(f'{(it.get("name") or "")[:40]}' for it in tl)
            vals = ' | '.join(str(d['v_of'](it)) for it in tl)
            w(f'| {d["doc"]} | {c} | {names} | {vals} |\n')
if not n_top:
    w('| — | — | дублей на верхнем уровне нет | — |\n')
print('дублей на верхнем уровне:', n_top)

# --- 3. аренда: где лежит и что с ней делает свод ---
w('\n## 3. Аренда: где лежит строка и что с ней делает свод\n\n')
w('| документ | строка аренды | код | цепочка | значение | вердикт свода |\n|---|---|---|---|---|---|\n')
n_lease = 0
for d in docs:
    for it in d['lease']:
        n_lease += 1
        chain = '/'.join(c for c in (it.get('_chain') or []) if c) or 'верхний уровень'
        note = next((x for x in d['notes'] if (it.get('name') or '')[:20] in x), '')
        verdict = 'долгоср.->1450' if 'долгоср' in note else (
            'краткоср.->1550' if 'краткоср' in note else ('не плюсовалась' if 'не плюсовалась' in note else note[:40] or '—'))
        w(f'| {d["doc"]} | {(it.get("name") or "")[:38]} | {it.get("code")} | {chain} | {d["v_of"](it)} | {verdict} |\n')
print('строк аренды всего:', n_lease)

# --- 4. что получает свод для 1550/1450 ---
w('\n## 4. Что свод кладёт в 1450 и 1550\n\n')
w('| документ | base1550 | аренда краткоср. | итог 1550 | base1450 | аренда долгоср. | итог 1450 | подозрение |\n|---|---|---|---|---|---|---|---|\n')
for d in docs:
    b1550, b1450 = d['base1550'], d['base1450']
    r1550 = (b1550 or 0) + d['short'] if d['short'] is not None else b1550
    r1450 = (b1450 or 0) + d['long'] if d['long'] is not None else b1450
    d['r1550'], d['r1450'] = r1550, r1450
    w(f'| {d["doc"]} | {b1550} | {d["short"]} | {r1550} | {b1450} | {d["long"]} | {r1450} | {"ДА" if d["susp"] else ""} |\n')

w('\n## 5. Детальные замечания rent_extract\n\n')
for d in docs:
    if d['notes']:
        w(f'\n### {d["doc"]}\n\n')
        for n in d['notes']:
            w(f'- {n}\n')

# --- 6. итог свода против эталона ---
w('\n## 6. Итог свода (1550, 1450) против эталона xlsx\n\n')
import openpyxl
XL = os.path.join(EX, 'svod_2025_2026.xlsx')
gold = {}
if os.path.exists(XL):
    wb = openpyxl.load_workbook(XL, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    hdr, yrs = rows[0], rows[1]
    for r in rows[2:]:
        nm = (r[0] or '').strip() if isinstance(r[0], str) else ''
        if not nm:
            continue
        for ci in range(1, len(hdr)):
            if not hdr[ci]:
                continue
            code = str(hdr[ci]).strip().split(' ')[0].split('+')[0]
            for off, yr in ((0, '2025'), (1, '2026')):
                if ci + off < len(r):
                    gold[(nm, code, yr)] = r[ci + off]

w('| документ | код | свод | эталон | вердикт |\n|---|---|---|---|---|\n')
bad = good = nogold = 0
for d in docs:
    doc = d['doc']
    m = re.match(r'^(.*)_6мес_(\d{4})$', doc)
    if not m:
        continue
    em, yr = m.group(1), m.group(2)
    for code, val in (('1550', d.get('r1550')), ('1450', d.get('r1450'))):
        g = gold.get((em, code, yr))
        gn = None if g is None else int(g)
        if gn is None and val is None:
            continue
        if gn is None:
            nogold += 1
            continue
        if val == gn:
            good += 1
            continue
        bad += 1
        diff = '' if val is None else f'{val - gn:+d}'
        w(f'| {doc} | {code} | {val} | {gn} | РАСХОЖДЕНИЕ {diff} |\n')
w(f'\nИтог: совпало {good}, расхождений {bad}, в эталоне пусто {nogold}.\n')
print(f'свод vs эталон (1550/1450): совпало {good}, расхождений {bad}')

out.close()
print('отчёт: _d43_inventory.md')
