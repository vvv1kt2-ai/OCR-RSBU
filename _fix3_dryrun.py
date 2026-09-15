# -*- coding: utf-8 -*-
r"""Сухой прогон правки 3: что меняется от добавления 1215 в правило 1200.

Пересчитываю проверки по СОХРАНЁННЫМ значениям (`items`) и сравниваю с сохранёнными
`checks`. Никаких вызовов моделей, ничего не пишется.
"""
import io, os, json, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
FORMS = ('balance', 'income_statement', 'cash_flow')

changed = []
still_bad = []
new_bad = []
for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    for form in FORMS:
        fd = doc.get(form) or {}
        items = fd.get('items') or []
        if not items:
            continue
        old = {c['rule']: c.get('ok') for c in (doc.get('checks') or []) if c['form'] == form}
        new = {c['rule']: c.get('ok') for c in P.run_checks(form, items)}
        for rule, ok_new in new.items():
            ok_old = old.get(rule)
            if ok_old is None:
                continue  # правило новое (имя изменилось) — сравнивать не с чем
            if ok_old != ok_new:
                changed.append((stem, form, rule, ok_old, ok_new))
        # провалы до и после, по совпадающим правилам
        old_fail = [r for r, v in old.items() if v is False]
        new_fail = [r for r, v in new.items() if v is False]
        if old_fail and not new_fail:
            still_bad.append((stem, form, 'исправлен', old_fail))
        elif new_fail and not old_fail:
            new_bad.append((stem, form, new_fail))

print('=== изменение состояния правил ===')
if not changed:
    print('изменений нет')
for stem, form, rule, o, n in changed:
    print('  %-32s %-17s %s: %s -> %s'
          % (stem[:32], form, rule[:46], o, n))
print()

print('=== документы, у которых провал ИСЧЕЗ ===')
for stem, form, _, old_fail in still_bad:
    print('  %-32s %-17s было провалено: %s' % (stem[:32], form, '; '.join(old_fail)))
print('всего: %d' % len(still_bad))
print()

print('=== документы, у которых провал ПОЯВИЛСЯ (не должно быть) ===')
for stem, form, new_fail in new_bad:
    print('  %-32s %-17s %s' % (stem[:32], form, new_fail))
print('всего: %d' % len(new_bad))
print()

print('=== сколько документов ещё проваливают правило 1200 ===')
n_bad = 0
for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    items = (doc.get('balance') or {}).get('items') or []
    if not items:
        continue
    for c in P.run_checks('balance', items):
        if c['rule'].startswith('1200') and c.get('ok') is False:
            n_bad += 1
            print('  %s  колонки: %s' % (stem, c['per_column']))
print('итого проваливают: %d' % n_bad)
