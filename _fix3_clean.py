# -*- coding: utf-8 -*-
r"""Правка 3, честный замер: старое правило против нового на ОДНИХ И ТОЛЬКО значениях.

Сохранённым `checks` доверять нельзя: `fix_forms.py` правил значения и `status`, но
проверки не пересчитывал (пример — ИПС_6мес_2026: ОДДС сходится, а `checks` говорят
ПРОВАЛ). Поэтому сравниваю две формулы правила 1200 на текущих `items`, воспроизводя
семантику конвейера (TOL = 2, `ok = all(...) and any(...)`).
"""
import io, os, json, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
TOL = 2
OLD = ('1210', '1220', '1230', '1240', '1250', '1260')
NEW = ('1210', '1215', '1220', '1230', '1240', '1250', '1260')


def per_column(items, codes, lhs='1200'):
    m = P.val_map(items)
    n = max((len(it['values']) for it in items if it.get('values')), default=0)
    def S(code, c):
        v = m.get(code) or []
        return v[c] if c < len(v) else None
    out = []
    for c in range(n):
        a = S(lhs, c)
        if a is None:
            out.append(None)
            continue
        rhs = sum(x for x in (S(k, c) for k in codes) if x is not None)
        out.append(abs(a - rhs) <= TOL)
    return out


def verdict(pc):
    return all(v is not False for v in pc) and any(v is True for v in pc)


print('%-32s %-22s %-22s %s' % ('документ', 'старое правило', 'новое правило', 'колонки'))
print('-' * 104)
fixed = []
still = []
for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    items = (doc.get('balance') or {}).get('items') or []
    if not items:
        continue
    po, pn = per_column(items, OLD), per_column(items, NEW)
    vo, vn = verdict(po), verdict(pn)
    if vo == vn and vo:
        continue
    print('%-32s %-22s %-22s %s' % (stem[:32], 'ПРОВАЛ' if not vo else 'прошла',
                                    'ПРОВАЛ' if not vn else 'прошла', pn))
    (fixed if (not vo and vn) else still).append((stem, vo, vn))
print('-' * 104)
print()
print('правило 1200:')
print('  проваливало (старое): %d документов' % len([1 for s, vo, vn in fixed + still if not vo]))
print('  проваливает (новое):  %d документов' % len([1 for s, vo, vn in fixed + still if not vn]))
print('  перестали проваливать: %d' % len(fixed))
for s, _, _ in fixed:
    print('     %s' % s)
print('  продолжают проваливать: %d' % len(still))
for s, _, _ in still:
    print('     %s' % s)
print()
print('=== появились ли новые провалы (не должно быть) ===')
bad = [(s, vo, vn) for s, vo, vn in fixed + still if vo and not vn]
print('  %d' % len(bad))
for s, vo, vn in bad:
    print('     %s' % s)
print()

# то же для правила 1100 (спящая дыра 1120/1130/1140)
OLD1 = ('1110', '1150', '1160', '1170', '1180', '1190')
NEW1 = ('1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180', '1190')
print('=== правило 1100 (спящие 1120/1130/1140) ===')
n_diff = 0
for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    items = (doc.get('balance') or {}).get('items') or []
    if not items:
        continue
    vo = verdict(per_column(items, OLD1, '1100'))
    vn = verdict(per_column(items, NEW1, '1100'))
    if vo != vn:
        n_diff += 1
        print('  %-32s %s -> %s' % (stem[:32], vo, vn))
print('  документов, где вердикт изменился: %d (ожидалось 0)' % n_diff)
