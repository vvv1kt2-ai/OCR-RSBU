# -*- coding: utf-8 -*-
r"""Честный итог по данным: только те формы, которые оба прогона собирались читать.

В пилоте документы 2025 года режутся до баланса (wanted_forms), и база тоже была в основном
такой: из 19 документов 2025 года ОФР есть только у 5, ОДДС у 3. Поэтому «пропало 383
значения» — в основном не потеря, а разница области. Здесь считаем строго:

  в области  — 2026: баланс + ОФР + ОДДС; 2025: только баланс;
  потеря     — значение, которое в бэкапе было, а в новом нет, И форма в области;
  приобретение — наоборот.

Так видно настоящий регресс, а не эффект сужения области.
"""
import io, json, os, re

OUT = r'D:\models\extracted'
BAK = os.path.join(OUT, '_backup_v2_before')
NEW = json.load(io.open(r'D:\models\_v2_прогон.json', encoding='utf-8'))
failed = {r['stem'] for r in NEW['rows'] if r['status'] in ('failed', None)}


def load(p):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except Exception:
        return None


def vals(r, key):
    d = (r or {}).get(key)
    if not d:
        return {}
    out = {}
    for it in (d.get('items') or []):
        code = str(it.get('code') or '').strip()
        if not code:
            continue
        for i, v in enumerate(it.get('values') or []):
            if v not in (None, ''):
                out[(code, i)] = str(v)
    return out


def in_scope(stem, key):
    if re.search(r'_2025$', stem):
        return key == 'balance'
    return True


stems = sorted(os.path.splitext(f)[0] for f in os.listdir(BAK)
               if f.endswith('.json') and not f.startswith('_'))
lost = gained = changed = same = 0
lost_by_doc = {}
term_lost = []
skipped_stale = []
for stem in stems:
    if stem in failed:
        skipped_stale.append(stem)
        continue
    o, n = load(os.path.join(BAK, stem + '.json')), load(os.path.join(OUT, stem + '.json'))
    if o is None or n is None:
        continue
    for key in ('balance', 'income_statement', 'cash_flow'):
        if not in_scope(stem, key):
            continue
        ov, nv = vals(o, key), vals(n, key)
        for k in set(ov) | set(nv):
            if k not in ov:
                gained += 1
            elif k not in nv:
                lost += 1
                lost_by_doc.setdefault('%s / %s' % (stem, key), []).append(k[0])
            elif ov[k] != nv[k]:
                changed += 1
            else:
                same += 1
        # замыкающий код
        oc = {c for c, _ in ov}
        nc = {c for c, _ in nv}
        term = {'balance': '1700', 'income_statement': '2400', 'cash_flow': '4500'}[key]
        if ov and term in oc and term not in nc:
            term_lost.append('%s / %s' % (stem, key))

print('документов в сравнении: %d (пропущено из-за сбоя: %d — их артефакт остался старым)'
      % (len(stems) - len(skipped_stale), len(skipped_stale)))
if skipped_stale:
    print('  упали: %s' % skipped_stale)
print()
print('=== значения строк, только формы в области')
print('  совпало:      %d' % same)
print('  появилось:    %d' % gained)
print('  изменилось:   %d' % changed)
print('  ПОТЕРЯНО:     %d' % lost)
print()
if lost_by_doc:
    print('=== где именно потеряно')
    for k in sorted(lost_by_doc, key=lambda x: -len(lost_by_doc[x])):
        codes = sorted(set(lost_by_doc[k]))
        print('  %-46s %2d значений: %s' % (k, len(lost_by_doc[k]), codes[:12]))
else:
    print('=== потерь нет')
print()
print('=== потерян замыкающий код: %d случаев' % len(term_lost))
for s in term_lost:
    print('   %s' % s)
