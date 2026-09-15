# -*- coding: utf-8 -*-
r"""Разбор потерь: Рекорд трейд_6мес_2026 / ОДДС (31 значение) и Моторные технологии_6мес_2025 / баланс (5).

Печатаем построчную разницу «бэкап -> новый артефакт», а также что говорит транскрипт страницы.
Потеря может быть трёх разных природ:
  * страницы не прочитаны (детекция увела их в notes);
  * страницы прочитаны, но структурирование потеряло строки;
  * эскалация заменила значения.
Поэтому смотрим и страницы, и сами значения, и предупреждения.
"""
import io, json, os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
BAK = os.path.join(OUT, '_backup_v2_before')
CASES = [('Рекорд трейд_6мес_2026', 'cash_flow'), ('Моторные технологии_6мес_2025', 'balance')]


def load(p):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except Exception:
        return None


def items(r, key):
    d = (r or {}).get(key)
    if not d:
        return {}
    return {str(it.get('code')): [('' if v is None else str(v)) for v in (it.get('values') or [])]
            for it in (d.get('items') or []) if it.get('code')}


for stem, key in CASES:
    o, n = load(os.path.join(BAK, stem + '.json')), load(os.path.join(OUT, stem + '.json'))
    print('=' * 96)
    print('%s / %s' % (stem, key))
    print('  бэкап: status=%-13s страницы=%s' % (o.get('status'), (o.get(key) or {}).get('transcript_pages')))
    print('  новый: status=%-13s страницы=%s' % (n.get('status'), (n.get(key) or {}).get('transcript_pages')))
    print('  text_layer: бэкап=%s новый=%s' % (o.get('source', {}).get('text_layer'),
                                               n.get('source', {}).get('text_layer')))
    print('  предупреждения нового:')
    for w in (n.get('warnings') or [])[:5]:
        print('     - %s' % w[:170])
    oi, ni = items(o, key), items(n, key)
    print('  строк: было %d, стало %d' % (len(oi), len(ni)))
    gone = [c for c in oi if c not in ni]
    new = [c for c in ni if c not in oi]
    diff = [(c, oi[c], ni[c]) for c in oi if c in ni and oi[c] != ni[c]]
    print('  пропали коды: %s' % sorted(gone))
    print('  появились:    %s' % sorted(new))
    for c in sorted(gone)[:8]:
        print('     %-6s было %s' % (c, oi[c]))
    print('  разошлись: %d' % len(diff))
    for c, a, b in diff[:6]:
        print('     %-6s %s -> %s' % (c, a, b))
    print()
