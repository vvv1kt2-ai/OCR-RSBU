# -*- coding: utf-8 -*-
"""Re-run pipeline checks on PRE-escalation values (values_ocr1) to size the damage
caused by the escalation cache collision."""
import os, json, glob

EX = r'D:\models\extracted'
REVIEW = ['КИФА_6мес_2026', 'КЛВЗ Кристалл_6мес_2025', 'КЛВЗ Кристалл_6мес_2026', 'Корпсан_6мес_2026',
          'Моторные технологии_6мес_2025', 'Органик парк_6мес_2025', 'Проект 111_6мес_2025',
          'Проект 111_6мес_2026', 'ТГК-14_6мес_2025', 'ТГК-14_6мес_2026', 'Эфферон_6мес_2025']


def val_map(items):
    m = {}
    for it in items or []:
        if it.get('code'):
            m.setdefault(it['code'], it.get('values'))
        for ch in it.get('children') or []:
            if ch.get('code'):
                m.setdefault(ch['code'], ch.get('values'))
    return m


def run_checks(form_key, items):
    m = val_map(items)
    n = max((len(it['values']) for it in items if it.get('values')), default=0)
    res = []
    def S(code, c):
        v = m.get(code, [None] * n)
        return v[c] if c < len(v) else None
    TOL = 2
    def eq(a, b): return a is not None and b is not None and abs(a - b) <= TOL
    def nz(*xs): return sum(x for x in xs if x is not None)
    def has(*xs): return any(x is not None for x in xs)
    if form_key == 'balance':
        rules = [
            ('1600 == 1700', lambda c: eq(S('1600', c), S('1700', c)) if has(S('1600', c)) else None),
            ('1100 == 1110+1150+1160+1170+1180+1190',
             lambda c: eq(S('1100', c), nz(*[S(k, c) for k in ('1110', '1150', '1160', '1170', '1180', '1190')])) if has(S('1100', c)) else None),
            ('1200 == 1210+1220+1230+1240+1250+1260',
             lambda c: eq(S('1200', c), nz(*[S(k, c) for k in ('1210', '1220', '1230', '1240', '1250', '1260')])) if has(S('1200', c)) else None),
            ('1300+1400+1500 == 1700',
             lambda c: eq(nz(S('1300', c), S('1400', c), S('1500', c)), S('1700', c)) if has(S('1700', c)) else None),
        ]
    else:
        return None
    for name, fn in rules:
        per_col = []
        for c in range(n):
            try:
                per_col.append(fn(c))
            except Exception:
                per_col.append(None)
        ok = all(v is not False for v in per_col) and any(v is True for v in per_col)
        res.append({'rule': name, 'per_column': per_col, 'ok': ok})
    return res


def with_values(items, key):
    """clone items with values := values_ocr1 where present"""
    out = []
    for it in items or []:
        j = dict(it)
        if j.get('values_ocr1') is not None:
            j['values'] = j['values_ocr1']
        ch = []
        for c in it.get('children') or []:
            k = dict(c)
            if k.get('values_ocr1') is not None:
                k['values'] = k['values_ocr1']
            ch.append(k)
        if ch:
            j['children'] = ch
        out.append(j)
    return out


print(f'{"документ":30} {"сейчас":>7} {"до эскалации":>13}  вывод')
for name in REVIEW:
    p = os.path.join(EX, name + '.json')
    if not os.path.exists(p):
        print(f'  {name:30} MISSING'); continue
    d = json.load(open(p, encoding='utf-8'))
    bal = d.get('balance')
    if not bal:
        print(f'  {name:30} {"—":>7} {"—":>13}  баланс отсутствует (другая причина)')
        continue
    now = run_checks('balance', bal['items'])
    pre = run_checks('balance', with_values(bal['items'], 'balance'))
    n_now = sum(1 for c in now if not c['ok'])
    n_pre = sum(1 for c in pre if not c['ok'])
    ncorr = sum(1 for it in bal['items'] if it.get('values_ocr1') is not None)
    verdict = ''
    if n_pre < n_now:
        verdict = f'ПРОВЕРКИ УЛУЧШАЮТСЯ без эскалации ({ncorr} подменённых строк)'
    print(f'  {name:30} {n_now}/4 упало {n_pre}/4 упало   {verdict}')

print('\n=== детально по ТГК-14 и Органик парк ===')
for name in ['ТГК-14_6мес_2025', 'ТГК-14_6мес_2026', 'Органик парк_6мес_2025']:
    d = json.load(open(os.path.join(EX, name + '.json'), encoding='utf-8'))
    bal = d['balance']
    print(f'\n--- {name} ---')
    for tag, items in (('сейчас', bal['items']), ('до эскалации', with_values(bal['items'], 'balance'))):
        chk = run_checks('balance', items)
        print(f'   {tag:14} ' + '; '.join(f'{c["rule"][:22]}={c["ok"]}{c["per_column"]}' for c in chk))
