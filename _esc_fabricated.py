# -*- coding: utf-8 -*-
r"""Разбор «выдуманных» чисел на эскалации: выдумали оба или врёт текстовый слой.

Если два разных поставщика выдают ОДНИ И ТЕ ЖЕ числа, которых нет в слое, то дело не в
моделях: это слой неполон. Проверяется сравнением множеств и поиском числа в самом PDF
(по всем страницам, а не только по той, что взяли).
"""
import io, os, json, sys

sys.path.insert(0, r'D:\models')
import _pv_quality as Q
import fitz

DL = r'D:\data-scraping\downloads'
rows = json.load(io.open(r'D:\models\_esc_quality.json', encoding='utf-8'))

print('=== совпадают ли множества «выдуманных» чисел ===')
same_all = 0
for r in rows:
    a, b = set(r['pz_bad']), set(r['pv_bad'])
    eq = a == b
    same_all += 1 if eq else 0
    print('  %-30s стр.%-3d Polza %2d, PlusVibe %2d, множества %s'
          % (r['stem'][:30], r['page'], len(a), len(b),
             'СОВПАДАЮТ' if eq else 'разные'))
    if not eq:
        print('      только у Polza:    %s' % sorted(a - b)[:8])
        print('      только у PlusVibe: %s' % sorted(b - a)[:8])
print('  совпало множеств: %d из %d' % (same_all, len(rows)))

print()
print('=== есть ли эти числа где-нибудь в PDF ===')
for r in rows:
    a = set(r['pz_bad'])
    if not a:
        continue
    pdf = os.path.join(DL, r['stem'] + '.pdf')
    if not os.path.exists(pdf):
        continue
    d = fitz.open(pdf)
    try:
        # искать по всем страницам и по обоим написаниям: с пробелами и без
        found = {}
        for n in sorted(a):
            hits = []
            for i in range(d.page_count):
                t = d[i].get_text()
                if n in t or Q.norm_digits(t).count(n):
                    hits.append(i + 1)
                    break
            if not hits:
                # попробуем с пробелом-разделителем тысяч
                if len(n) >= 5:
                    spaced = n[:-3] + ' ' + n[-3:]
                    for i in range(d.page_count):
                        if spaced in d[i].get_text():
                            hits.append(i + 1)
                            break
            found[n] = hits
        n_found = sum(1 for v in found.values() if v)
        print('  %-30s стр.%-3d «выдуманных» %2d, найдено в PDF: %2d'
              % (r['stem'][:30], r['page'], len(a), n_found))
        for n, v in sorted(found.items()):
            if not v:
                print('      нет нигде: %s' % n)
            elif r['page'] not in v:
                print('      есть, но на другой странице (%s): %s' % (v[:4], n))
    finally:
        d.close()
