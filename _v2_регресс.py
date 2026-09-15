# -*- coding: utf-8 -*-
r"""Разбор двух подозрительных документов: ИПС_6мес_2026 (потерял всё) и Афанасий_6мес_2025.

Первый: в бэкапе было 23/14/12 строк по трём формам, в новом прогоне 0/0/0.
Второй: баланс 37 строк -> 34.

Печатаем предупреждения и построчную разницу, чтобы понять, это регресс кода, отказ
поставщика или следствие сужения области (2025 -> только баланс).
"""
import io, json, os

OUT = r'D:\models\extracted'
BAK = os.path.join(OUT, '_backup_v2_before')


def load(p):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except Exception:
        return None


def items(r, key):
    d = (r or {}).get(key)
    if not d:
        return {}
    return {str(it.get('code')): [str(v) if v is not None else '' for v in (it.get('values') or [])]
            for it in (d.get('items') or []) if it.get('code')}


for stem in ('ИПС_6мес_2026', 'Афанасий_6мес_2025'):
    o = load(os.path.join(BAK, stem + '.json'))
    n = load(os.path.join(OUT, stem + '.json'))
    print('=' * 92)
    print('%s' % stem)
    print('  бэкап: status=%s checks=%d (False=%d)'
          % (o.get('status'), len(o.get('checks') or []),
             sum(1 for c in (o.get('checks') or []) if c.get('ok') is False)))
    print('  новый: status=%s checks=%d (False=%d)'
          % (n.get('status'), len(n.get('checks') or []),
             sum(1 for c in (n.get('checks') or []) if c.get('ok') is False)))
    print('  предупреждения нового:')
    for w in (n.get('warnings') or [])[:6]:
        print('     - %s' % w[:180])
    print('  страницы:')
    for k in ('balance', 'income_statement', 'cash_flow'):
        po = (o.get(k) or {}).get('transcript_pages')
        pn = (n.get(k) or {}).get('transcript_pages')
        print('     %-17s было %s -> стало %s' % (k, po, pn))
    print('  разница по балансу:')
    oi, ni = items(o, 'balance'), items(n, 'balance')
    only_o = [k for k in oi if k not in ni]
    only_n = [k for k in ni if k not in oi]
    diff = [(k, oi[k], ni[k]) for k in oi if k in ni and oi[k] != ni[k]]
    print('     только в бэкапе: %s' % only_o[:16])
    print('     только в новом:  %s' % only_n[:16])
    print('     разошлись: %d' % len(diff))
    for k, a, b in diff[:6]:
        print('        %-6s %s -> %s' % (k, a, b))
    print()
