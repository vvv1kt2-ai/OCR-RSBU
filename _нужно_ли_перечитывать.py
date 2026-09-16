# -*- coding: utf-8 -*-
r"""Нужно ли эскалации ПЕРЕЧИТЫВАТЬ страницу, или достаточно переразобрать оплаченный текст?

Эскалация делает два дорогих шага: расшифровывает страницы заново (дорогая модель, 300 dpi)
и структурирует результат. Но у остаточных провалов не хватает СТРОК, а не цифр: у
«ИПС_6мес_2025» строка 1520 = 15307 напечатана в транскрипте, который УЖЕ оплачен.

Здесь проверяем по каждому остаточному провалу: присутствует ли недостающее слагаемое в
оплаченных транскриптах 200 dpi основной модели. Если да — перечитывание страницы не нужно,
достаточно переразобрать имеющийся текст, и это вдвое дешевле.

Вызовов моделей нет: только чтение оплаченного кэша.
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
DOCS = ['Корпсан_6мес_2026', 'ИПС_6мес_2025', 'Моторные технологии_6мес_2025',
        'Эфферон_6мес_2025', 'Органик парк_6мес_2025', 'ТГК-14_6мес_2025']


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


def paid_text(doc, form_key, provider_suffix='_pv'):
    """текст всех оплаченных транскриптов основной модели по этому документу"""
    stem = doc
    hits = []
    for f in glob.glob(os.path.join(PAGES, f'{stem}_p*_200_*{provider_suffix}*.md')):
        hits.append(f)
    if not hits:   # без суффикса поставщика
        for f in glob.glob(os.path.join(PAGES, f'{stem}_p*_200_*.md')):
            hits.append(f)
    out = {}
    for f in hits:
        m = re.search(r'_p(\d+)_200_', os.path.basename(f))
        if m:
            out[int(m.group(1))] = io.open(f, encoding='utf-8', errors='replace').read()
    return out


print('проверка: есть ли недостающее слагаемое в УЖЕ ОПЛАЧЕННОМ тексте 200 dpi')
print()
for doc in DOCS:
    p = os.path.join(EX, doc + '.json')
    if not os.path.exists(p):
        continue
    j = json.load(io.open(p, encoding='utf-8'))
    items = (j.get('balance') or {}).get('items') or []
    if not items:
        continue
    new = as_new_code(copy.deepcopy(items), 'balance')
    bad = [c for c in P.run_checks('balance', new)
           if not c['ok'] and any(v is False for v in c['per_column'])]
    if not bad:
        continue
    pages = (j.get('balance') or {}).get('transcript_pages') or []
    texts = paid_text(doc, 'balance')
    blob = '\n'.join(texts.values())
    blob_flat = re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', blob)
    print(f'=== {doc}   оплаченных страниц 200 dpi: {len(texts)} (в артефакте: {pages})')
    m = P.val_map(new)
    for c in bad:
        total = c['rule'][:4]
        if total not in PARTS:
            continue
        for i in [x for x, v in enumerate(c['per_column']) if v is False]:
            tv = (m.get(total) or [None] * 4)[i]
            add = [(k, (m.get(k) or [None] * 4)[i]) for k in PARTS[total]]
            s = sum(v for _, v in add if v is not None)
            miss = tv - s if tv is not None else None
            if not miss:
                continue
            needle = str(abs(miss))
            found = needle in blob_flat
            where = [pg for pg, t in texts.items()
                     if needle in re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', t)]
            print(f"  {total} кол.{i}: не хватает {miss:+}  ->  число {needle} "
                  f"в оплаченном тексте: {'ЕСТЬ' if found else 'НЕТ'}"
                  + (f' (стр. {sorted(where)})' if found else ''))
    print()
