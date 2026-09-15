# -*- coding: utf-8 -*-
r"""Промежуточный просмотр: совпали ли два групповых прогона (режим A)."""
import io, json, os, sys, collections

PAGES = r'D:\models\extracted\pages'
STEM = sys.argv[1] if len(sys.argv) > 1 else 'НовосибирскАвтодор_6мес_2025'


def lab(tag):
    p = os.path.join(PAGES, f'_llm_{STEM}_detect_{tag}_g2_pv.json')
    if not os.path.exists(p):
        return None
    pm = json.load(io.open(p, encoding='utf-8'))
    return {r['page']: r.get('form') for r in pm
            if isinstance(r, dict) and isinstance(r.get('page'), int)}


MODE = sys.argv[2] if len(sys.argv) > 2 else 'A'
a1, a2 = lab(MODE + '1'), lab(MODE + '2')
print('документ: %s' % STEM)
if a1 is None or a2 is None:
    print('прогоны A ещё не готовы'); sys.exit(0)
n = max(max(a1 or {0}), max(a2 or {0}))
print('страниц в метках: A1=%d, A2=%d' % (len(a1), len(a2)))
print()
print('стр. | A1              | A2')
diff = []
for p in range(1, n + 1):
    x, y = a1.get(p), a2.get(p)
    mark = '' if x == y else '  <-- РАСХОЖДЕНИЕ'
    if x != y:
        diff.append(p)
    print('%4d | %-15s | %-15s%s' % (p, x, y, mark))
print()
same = sum(1 for p in range(1, n + 1) if a1.get(p) == a2.get(p))
print('совпало: %d из %d (%.0f%%)' % (same, n, 100.0 * same / n))
print()
print('страниц форм: A1=%s' % dict(collections.Counter(
    v for v in a1.values() if v in ('balance', 'income_statement', 'cash_flow'))))
print('              A2=%s' % dict(collections.Counter(
    v for v in a2.values() if v in ('balance', 'income_statement', 'cash_flow'))))
