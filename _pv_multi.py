# -*- coding: utf-8 -*-
"""Разбор расхождений по классам: совсем нет / есть, но реже / лишнее.

Нужен, чтобы вердикт не путал «число потеряно» с «число встречается реже»:
в таблицах остаток на начало года равен остатку на конец прошлого года, поэтому
одно и то же число законно стоит в двух ячейках.

    python _pv_multi.py
"""
import io, os, sys
from collections import Counter

sys.path.insert(0, r'D:\models')
import _pv_quality as Q

PAGES = os.path.join(Q.EX, 'pages')
CACHE = os.path.join(PAGES, '_pvq')
REPORT = r'D:\models\_pv_quality.json'
OUT = r'D:\models\_pv_multi.md'


def main():
    d = io.open(REPORT, encoding='utf-8')
    data = __import__('json').load(d)
    d.close()

    lines = []
    tot = {'absent_sig': 0, 'under_sig': 0, 'absent_any': 0, 'under_any': 0}
    for r in data['rows']:
        ref = io.open(os.path.join(PAGES, r['ref_file']), encoding='utf-8').read()
        cand = io.open(os.path.join(CACHE, r['pv_file']), encoding='utf-8').read()
        cr, cc = Counter(Q.norm_digits(ref)), Counter(Q.norm_digits(cand))
        absent = sorted((cr - cc).elements())
        extra = sorted((cc - cr).elements())
        # реже — число есть, но встречается меньше раз: значит выпала строка
        und = [(n, cr[n], cc[n]) for n in sorted(set(cr) & set(cc)) if cc[n] < cr[n]]
        a_sig = Q.significant(absent)
        u_sig = Q.significant([n for n, _, _ in und])
        tot['absent_sig'] += len(a_sig)
        tot['under_sig'] += len(u_sig)
        tot['absent_any'] += len(absent)
        tot['under_any'] += len(und)
        lines.append('%-30s стр.%-3d симв %5d->%5d | нет совсем %3d (значимых %2d) | '
                     'реже %3d (значимых %2d) | лишних %3d'
                     % (r['stem'][:30], r['page'], r['len_polza'], r['len_pv'],
                        len(absent), len(a_sig), len(und), len(u_sig), len(extra)))
        if a_sig:
            lines.append('      нет совсем: ' + ', '.join(a_sig[:8]))
        if u_sig:
            lines.append('      реже: '
                         + ', '.join('%s(%d->%d)' % x for x in und if len(x[0]) >= 4)[:160])

    io.open(OUT, 'w', encoding='utf-8').write(
        '# Классы расхождений\n\n' + '\n'.join(lines) +
        '\n\nИтого: нет совсем %d (значимых %d); реже %d (значимых %d)\n'
        % (tot['absent_any'], tot['absent_sig'], tot['under_any'], tot['under_sig']))
    print('\n'.join(lines))
    print('\nИтого: нет совсем %d (значимых %d); реже %d (значимых %d)'
          % (tot['absent_any'], tot['absent_sig'], tot['under_any'], tot['under_sig']))


if __name__ == '__main__':
    main()
