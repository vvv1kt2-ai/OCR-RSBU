# -*- coding: utf-8 -*-
r"""Сколько страниц реально прочитано и во сколько это обошлось (по артефактам, бесплатно).

Считает по артефактам `extracted\*.json`: сколько всего страниц в документах и сколько из
них реально попало в чтение (транскрипты форм + титульный лист). Это нужно, чтобы
сравнивать цену за страницу с тарифами других распознавателей на одном основании.
"""
import io, json, os, sys

OUT = r'D:\models\extracted'
arts = [f for f in os.listdir(OUT) if f.endswith('.json') and not f.startswith('_')]
print('артефактов: %d' % len(arts))

pages_total = 0
pages_read = set()
docs = 0
by_provider = {}
for fn in arts:
    try:
        r = json.load(io.open(os.path.join(OUT, fn), encoding='utf-8'))
    except Exception:
        continue
    docs += 1
    src = r.get('source') or {}
    pages_total += src.get('pages_total') or 0
    prov = src.get('provider') or 'не записан'
    by_provider[prov] = by_provider.get(prov, 0) + 1
    for k in ('balance', 'income_statement', 'cash_flow'):
        d = r.get(k)
        if not d:
            continue
        for p in (d.get('transcript_pages') or []):
            pages_read.add((fn, p))

print('документов: %d' % docs)
print('страниц во всех документах: %d' % pages_total)
print('страниц реально прочитано (уникальных, по формам): %d' % len(pages_read))
print()
print('поставщик в артефактах:')
for k, v in sorted(by_provider.items(), key=lambda kv: -kv[1]):
    print('   %-24s %d документов' % (k, v))
print()
man = os.path.join(OUT, '_manifest.json')
if os.path.exists(man):
    m = json.load(io.open(man, encoding='utf-8'))
    u = m.get('usage') or {}
    print('последний манифест: %s' % m.get('generated'))
    print('   поставщик: %s' % m.get('provider'))
    print('   вызовов: %s, токены %s/%s, стоимость %s ₽'
          % (u.get('calls'), u.get('prompt'), u.get('completion'), u.get('cost_rub')))
    print('   (это последний прогон, а не весь корпус)')
