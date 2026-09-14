# -*- coding: utf-8 -*-
"""Третейский судья: сверка обоих транскриптов с текстовым слоем самого PDF.

Качество поставщика нельзя мерить только сравнением с эталоном Polza: если эталон
сам ошибается, «расхождение» означает не дефект проверяемого, а дефект эталона.
Текстовый слой PDF — независимый и бесплатный источник истины там, где он есть.

Для каждой страницы выборки считаем, сколько чисел каждого ответа подтверждается
текстовым слоем, и сколько не подтверждается ничем (то есть придумано).
"""
import io, os, sys, json
from collections import Counter

sys.path.insert(0, r'D:\models')
sys.path.insert(0, r'D:\models\pylibs')
import pymupdf
import _pv_quality as Q

P = os.path.join(Q.EX, 'pages')
C = os.path.join(P, '_pvq')


def layer_nums(doc, page):
    t = doc[page - 1].get_text()
    return Q.norm_digits(t), len(t.replace(' ', '').replace('\u00a0', ''))


def probe(report_json, variant):
    d = json.load(io.open(report_json, encoding='utf-8'))
    docs, out = {}, []
    for r in d['rows']:
        pdf = os.path.join(Q.DL, r['stem'] + '.pdf')
        if pdf not in docs:
            docs[pdf] = pymupdf.open(pdf)
        lay, rawlen = layer_nums(docs[pdf], r['page'])
        cl = Counter(lay)
        ref = io.open(os.path.join(P, r['ref_file']), encoding='utf-8').read()
        cand = io.open(os.path.join(C, r['pv_file']), encoding='utf-8').read()
        def confirmed(txt):
            """сколько чисел ответа есть в текстовом слое и сколько нет"""
            nums = Q.norm_digits(txt)
            ok = sum(1 for n in nums if cl[n])
            bad = [n for n in nums if not cl[n] and len(n) >= 4]
            return len(nums), ok, len(bad), bad[:6]
        rn, rok, rbad, rex = confirmed(ref)
        cn, cok, cbad, cex = confirmed(cand)
        out.append({'stem': r['stem'], 'page': r['page'], 'layer': rawlen,
                    'ref_n': rn, 'ref_ok': rok, 'ref_bad': rbad, 'ref_ex': rex,
                    'pv_n': cn, 'pv_ok': cok, 'pv_bad': cbad, 'pv_ex': cex,
                    'verdict': d['verdict']['ok']})
    return out


def main():
    rows = probe(r'D:\models\_pv_quality.json', 'default')
    lines = ['# Сверка с текстовым слоем PDF (третейский судья)', '',
             'Для страниц, где текстовый слой есть, видно, кто именно ошибся: эталон Polza',
             'или ответ PlusVibe. «Придумано» — числа длиной 4+ знака, которых нет в слое.', '',
             '| документ | стр. | слой, знаков | чисел Polza | подтверждено | придумано | '
             'чисел PlusVibe | подтверждено | придумано |', '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append('| %s | %d | %d | %d | %d | %d | %d | %d | %d |'
                     % (r['stem'], r['page'], r['layer'], r['ref_n'], r['ref_ok'], r['ref_bad'],
                        r['pv_n'], r['pv_ok'], r['pv_bad']))
    lines += ['', '## Страницы, где ошибся эталон Polza (его числа не подтверждаются слоем)', '']
    ref_guilty = [r for r in rows if r['layer'] > 200 and r['ref_bad'] > 0]
    for r in ref_guilty:
        lines.append('- %s стр.%d: придумано %d чисел, например %s'
                     % (r['stem'], r['page'], r['ref_bad'], ', '.join(r['ref_ex'])))
    if not ref_guilty:
        lines.append('нет')
    lines += ['', '## Страницы, где ошибся PlusVibe', '']
    pv_guilty = [r for r in rows if r['layer'] > 200 and r['pv_bad'] > 0]
    for r in pv_guilty:
        lines.append('- %s стр.%d: придумано %d чисел, например %s'
                     % (r['stem'], r['page'], r['pv_bad'], ', '.join(r['pv_ex'])))
    if not pv_guilty:
        lines.append('нет')
    lines += ['', '## Итог по страницам с пригодным слоем', '']
    usable = [r for r in rows if r['layer'] > 200]
    lines.append('- страниц с пригодным текстовым слоем: %d из %d' % (len(usable), len(rows)))
    lines.append('- у Polza придумано чисел: %d' % sum(r['ref_bad'] for r in usable))
    lines.append('- у PlusVibe придумано чисел: %d' % sum(r['pv_bad'] for r in usable))
    io.open(r'D:\models\_pv_arbiter.md', 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    # Машинный итог рядом с отчётом: вердикт должен читать поля, а не искать
    # подстроки в готовом markdown — иначе он сломается от правки формулировки.
    json.dump({'pages_total': len(rows), 'pages_usable': len(usable),
               'ref_fabricated': sum(r['ref_bad'] for r in usable),
               'pv_fabricated': sum(r['pv_bad'] for r in usable),
               'ref_guilty_pages': [f'{r["stem"]}:{r["page"]}' for r in ref_guilty],
               'pv_guilty_pages': [f'{r["stem"]}:{r["page"]}' for r in pv_guilty]},
              io.open(r'D:\models\_pv_arbiter.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
