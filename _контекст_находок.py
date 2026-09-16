# -*- coding: utf-8 -*-
r"""Два вопроса к остаточным провалам, оба бесплатные.

1. Совпадение «число есть в оплаченном тексте» может быть случайным (4000 встретится и в
   чужой строке). Печатаем СТРОКУ транскрипта, в которой число найдено, — только по ней
   можно судить, та это строка или нет.
2. У ТГК-14_6мес_2025 правило 1100 расходится на 2.2 млн во ВСЕХ колонках, причём сумма
   БОЛЬШЕ итога — это признак двойного счёта, а не пропажи. Печатаем слагаемые.
"""
import copy
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
PARTS = {
    '1100': ('1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180', '1190'),
    '1200': ('1210', '1215', '1220', '1230', '1240', '1250', '1260'),
    '1400': ('1410', '1420', '1430', '1440', '1450'),
    '1500': ('1510', '1520', '1530', '1540', '1550'),
}


def as_new_code(items, form_key):
    top = {it.get('code') for it in items if it.get('code')}
    out = []
    for it in items:
        cur = dict(it); cur['children'] = list(it.get('children') or [])
        kids, keep = [], []
        for ch in cur['children']:
            c = ch.get('code')
            (kids if (c and c in top) else keep).append(ch)
        cur['children'] = keep; out.append(cur); out.extend(kids)
    out = P.merge_duplicate_codes(out, [], form_key)
    if form_key == 'balance':
        P._assign_bal_codes(out)
    return out


def paid_pages(doc):
    out = {}
    for f in glob.glob(os.path.join(PAGES, f'{doc}_p*_200_*.md')):
        m = re.search(r'_p(\d+)_200_', os.path.basename(f))
        if m:
            out.setdefault(int(m.group(1)), []).append(f)
    return out


def context_lines(text, needle):
    flat_lines = text.splitlines()
    hits = []
    for ln in flat_lines:
        if needle in re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', ln):
            hits.append(ln.strip()[:150])
    return hits[:3]


CASES = [
    ('Корпсан_6мес_2026', 'balance', '4000'),
    ('Моторные технологии_6мес_2025', 'balance', '14500'),
    ('Моторные технологии_6мес_2025', 'balance', '87800'),
    ('Эфферон_6мес_2025', 'balance', '59000'),
    ('Органик парк_6мес_2025', 'balance', '28551'),
]
print('=== 1. КОНТЕКСТ найденных чисел (та ли это строка?)')
for doc, fk, needle in CASES:
    pages = paid_pages(doc)
    print(f'\n--- {doc}: ищем {needle}')
    for pg in sorted(pages):
        for f in pages[pg]:
            t = io.open(f, encoding='utf-8', errors='replace').read()
            for ln in context_lines(t, needle):
                print(f'  стр.{pg} [{os.path.basename(f)[-22:]}]: {ln}')

print('\n\n=== 2. СОСТАВ СЛАГАЕМЫХ там, где сумма БОЛЬШЕ итога')
for doc in ('ТГК-14_6мес_2025', 'Органик парк_6мес_2025'):
    p = os.path.join(EX, doc + '.json')
    j = json.load(io.open(p, encoding='utf-8'))
    items = (j.get('balance') or {}).get('items') or []
    new = as_new_code(copy.deepcopy(items), 'balance')
    m = P.val_map(new)
    print(f'\n--- {doc}')
    for total in ('1100', '1200', '1400', '1500'):
        tv = m.get(total)
        if not tv:
            continue
        add = [(k, m.get(k)) for k in PARTS[total]]
        for i in range(len(tv)):
            if tv[i] is None:
                continue
            have = [(k, v[i]) for k, v in add if v and i < len(v) and v[i] is not None]
            s = sum(v for _, v in have)
            mark = '  <<< БОЛЬШЕ' if s > tv[i] + 2 else ''
            print(f'  {total} кол.{i}: итог={tv[i]} сумма={s} разница={tv[i]-s:+}{mark}')
            print('     ' + ', '.join(f'{k}={v}' for k, v in have))
