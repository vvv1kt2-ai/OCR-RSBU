# -*- coding: utf-8 -*-
r"""Честный итог по данным: сравнение по КОДАМ, как это делает свод.

Два предыдущих варианта этого сравнения были неверны, и оба врали:
  1) читал только верхний уровень items -> объявил 31 значение потерянным у «Рекорд трейд»,
     хотя детализация просто переехала во вложенные строки (полный обход даёт те же 57 ячеек);
  2) читал вложенные, но строки БЕЗ кода сопоставлял по позиции -> получил 427 «потерь»,
     потому что порядок вложенных строк между прогонами нестабилен, и одинаковые данные
     разошлись по разным меткам.

Правильный способ — тот же, что у свода (`svod.get_val`): адресуемся по 4-значному КОДУ и
берём ПОСЛЕДНЕЕ вхождение. Строки без кода (детализация «в том числе») в свод не попадают и
по кодам не адресуются, поэтому их считаем отдельно — числом, а не сопоставлением.

Область: 2025 год — только баланс (wanted_forms), 2026 — все три формы.
"""
import io, json, os, re, collections

OUT = r'D:\models\extracted'
BAK = os.path.join(OUT, '_backup_v2_before')
CODE = re.compile(r'^\d{4}$')


def load(p):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except Exception:
        return None


def by_code(r, key):
    """код -> значения, по последнему вхождению (как svod.get_val); плюс число строк без кода"""
    d = (r or {}).get(key)
    if not d:
        return {}, 0
    out, uncoded = {}, 0

    def rec(items):
        nonlocal uncoded
        for it in items or []:
            c = str(it.get('code') or '').strip()
            if CODE.match(c):
                out[c] = [('' if v is None else str(v)) for v in (it.get('values') or [])]
            else:
                uncoded += 1
            rec(it.get('children'))
    rec(d.get('items'))
    return out, uncoded


def in_scope(stem, key):
    return key == 'balance' if re.search(r'_2025$', stem) else True


stems = sorted(os.path.splitext(f)[0] for f in os.listdir(BAK)
               if f.endswith('.json') and not f.startswith('_'))
same = gained = changed = lost = 0
lost_by_doc = collections.defaultdict(list)
uncoded_delta = 0
for stem in stems:
    o, n = load(os.path.join(BAK, stem + '.json')), load(os.path.join(OUT, stem + '.json'))
    if o is None or n is None:
        continue
    for key in ('balance', 'income_statement', 'cash_flow'):
        if not in_scope(stem, key):
            continue
        ov, ouc = by_code(o, key)
        nv, nuc = by_code(n, key)
        uncoded_delta += nuc - ouc
        for c, vals in ov.items():
            if c not in nv:
                lost += sum(1 for v in vals if v != '')
                lost_by_doc['%s / %s' % (stem, key)].append(c)
                continue
            nvals = nv[c]
            for i, v in enumerate(vals):
                w = nvals[i] if i < len(nvals) else ''
                if v == w:
                    same += 1
                elif v == '' and w != '':
                    gained += 1
                elif v != '' and w == '':
                    lost += 1
                    lost_by_doc['%s / %s' % (stem, key)].append('%s[%d]' % (c, i))
                else:
                    changed += 1
        for c, vals in nv.items():
            if c not in ov:
                gained += sum(1 for v in vals if v != '')

print('документов сверено: %d (41 = весь пилот)' % len(stems))
print()
print('=== по кодам, только формы в области')
print('  совпало:    %d' % same)
print('  появилось:  %d' % gained)
print('  изменилось: %d' % changed)
print('  ПОТЕРЯНО:   %d' % lost)
print('  строк без кода: %+d (детализация «в том числе», в свод не входит)' % uncoded_delta)
print()
if lost_by_doc:
    print('=== где потеряно')
    for k in sorted(lost_by_doc, key=lambda x: -len(lost_by_doc[x])):
        print('  %-46s %3d: %s' % (k, len(lost_by_doc[k]),
                                   sorted(set(lost_by_doc[k]))[:10]))
else:
    print('=== по кодам потерь нет')
