# -*- coding: utf-8 -*-
r"""Сводный разбор остаточного спроса на эскалацию: что из него — правда чтение, а что — наше.

Для каждого документа, который под новым кодом всё ещё валит проверку, отвечаем на три
вопроса, не тратя ни рубля:
  1) какого слагаемого не хватает и на сколько расходится;
  2) есть ли это число в УЖЕ ОПЛАЧЕННОМ транскрипте, в строке с нужным кодом (сильное
     совпадение) — тогда перечитывать страницу незачем;
  3) не лежит ли верное значение в values_ocr1, то есть не испортила ли его эскалация;
     и поймал бы это нынешний escalation_gate.
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
DOCS = ['Корпсан_6мес_2026', 'ИПС_6мес_2026', 'Простая еда_6мес_2025', 'ТГК-14_6мес_2026',
        'ИПС_6мес_2025', 'Моторные технологии_6мес_2025', 'Органик парк_6мес_2025',
        'ТГК-14_6мес_2025', 'Эфферон_6мес_2025']


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


def swap_values(items, key):
    out = copy.deepcopy(items)
    for it in out:
        if it.get(key) is not None:
            it['values'] = copy.deepcopy(it[key])
        for ch in it.get('children') or []:
            if ch.get(key) is not None:
                ch['values'] = copy.deepcopy(ch[key])
    return out


def paid_lines(doc):
    out = []
    for f in glob.glob(os.path.join(PAGES, f'{doc}_p*_*.md')):
        m = re.search(r'_p(\d+)_', os.path.basename(f))
        t = io.open(f, encoding='utf-8', errors='replace').read()
        out.append((int(m.group(1)) if m else 0, os.path.basename(f), t))
    return out


def find_with_code(texts, number, codes):
    """строки, где число стоит рядом с одним из кодов — сильное совпадение"""
    hits = []
    for pg, fn, t in texts:
        for ln in t.splitlines():
            flat = re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', ln)
            if str(number) not in flat:
                continue
            for c in codes:
                if re.search(r'\|\s*' + c + r'\s*\|', flat):
                    hits.append((pg, ln.strip()[:130]))
                    break
    return hits


for doc in DOCS:
    p = os.path.join(EX, doc + '.json')
    if not os.path.exists(p):
        print(f'{doc}: нет артефакта'); continue
    j = json.load(io.open(p, encoding='utf-8'))
    print(f'\n{"="*74}\n{doc}')
    warns = [w for w in (j.get('warnings') or []) if 'эскал' in str(w).lower()]
    if warns:
        print(f'  предупреждения об эскалации: {len(warns)}')
    for fk in ('balance', 'income_statement', 'cash_flow'):
        items = (j.get(fk) or {}).get('items') or []
        if not items:
            continue
        new = as_new_code(copy.deepcopy(items), fk)
        bad = [c for c in P.run_checks(fk, new)
               if not c['ok'] and any(v is False for v in c['per_column'])]
        if not bad:
            continue
        m = P.val_map(new)
        texts = paid_lines(doc)
        for c in bad:
            total = c['rule'][:4]
            print(f"  ВАЛИТ {c['rule'][:44]}")
            if total not in PARTS:
                continue
            for i in [x for x, v in enumerate(c['per_column']) if v is False]:
                tv = (m.get(total) or [None] * 4)[i]
                add = [(k, (m.get(k) or [None] * 4)[i]) for k in PARTS[total]]
                s = sum(v for _, v in add if v is not None)
                if tv is None:
                    continue
                miss = tv - s
                if abs(miss) <= 2:
                    continue
                hits = find_with_code(texts, abs(miss), PARTS[total])
                print(f"    кол.{i}: не хватает {miss:+}  "
                      f"в оплаченном тексте рядом с кодом: "
                      f"{'ЕСТЬ стр.' + str(sorted({h[0] for h in hits})) if hits else 'НЕТ'}")
                for pg, ln in hits[:2]:
                    print(f"       стр.{pg}: {ln}")
    # гейт: откатили бы values к values_ocr1?
    items = (j.get('balance') or {}).get('items') or []
    if items and any(it.get('values_ocr1') is not None for it in items):
        before = swap_values(items, 'values_ocr1')
        after = as_new_code(copy.deepcopy(items), 'balance')
        try:
            ok, why = P.escalation_gate('balance', before, after)
            print(f'  ГЕЙТ на (values_ocr1 -> values): {"ПРОПУСТИЛ" if ok else "ОТКЛОНИЛ"} — {why}')
        except Exception as e:
            print(f'  ГЕЙТ: ошибка вызова — {type(e).__name__}: {e}')
