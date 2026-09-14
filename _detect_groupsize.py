# -*- coding: utf-8 -*-
r"""Доля отказов в зависимости от размера группы — от неё зависит потеря форм.

Конвейер при отказе группы делит её пополам и повторяет (`pipeline.py:910-917`), а
страницы пропускает только если провалилась группа из двух страниц. Значит судьба
формы решается не общей долей отказов, а долей отказов на маленькой группе.

Здесь измеряются группы 8, 4 и 2 страницы. Стоит копейки.
"""
import io, json, os, sys, urllib.request, statistics

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR
import fitz

DL = r'D:\data-scraping\downloads'
DOC = 'Моторные технологии_6мес_2025'


def call(doc_obj, group, npages, prof, key):
    cm = [{'role': 'user', 'content': [
        {'type': 'text',
         'text': P.DETECT_PROMPT + f' (Страницы {group[0]}-{group[-1]} из {npages})'}]}]
    for j in group:
        cm[0]['content'].extend(
            P.img_parts(P.render_png(doc_obj[j - 1], 120), f'СТРАНИЦА {j}'))
    url, headers, body = PR.build_request(prof, P.M_DETECT, cm, key,
                                          temperature=0, max_tokens=1200)
    req = urllib.request.Request(url, data=body, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.loads(r.read())
        u = resp.get('usage') or {}
        det = u.get('completion_tokens_details') or {}
        txt = resp['choices'][0]['message']['content'] or ''
        return {'ok': True, 'reasoning': det.get('reasoning_tokens') or 0,
                'ct': u.get('completion_tokens') or 0,
                'parsed': len(P.salvage_pages_map(txt, npages))}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'code': e.code}
    except Exception:
        return {'ok': False, 'code': '?'}


def main():
    n = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 20
    prof = PR.active()
    key = PR.load_key(prof)
    pdf = os.path.join(DL, DOC + '.pdf')
    d = fitz.open(pdf)
    npages = d.page_count
    print('поставщик: %s, документ: %s (страниц %d)' % (prof.name, DOC, npages))
    print('вызовов на размер группы: %d' % n)
    print()
    print('%-9s %8s %8s %9s %14s %14s'
          % ('группа', 'вызовов', 'отказов', 'доля', 'рассужд медиана', 'рассужд макс'))
    print('-' * 70)
    out = {}
    for size in (8, 4, 2):
        runs = []
        for i in range(n):
            g = list(range(1, size + 1))
            runs.append(call(d, g, npages, prof, key))
        fails = [r for r in runs if not r['ok']]
        oks = [r for r in runs if r['ok']]
        rs = [r['reasoning'] for r in oks] or [0]
        print('%-9d %8d %8d %8.0f%% %14d %14d'
              % (size, len(runs), len(fails), 100 * len(fails) / len(runs),
                 statistics.median(rs), max(rs)))
        out[str(size)] = {'runs': len(runs), 'fails': len(fails),
                          'reasoning_median': statistics.median(rs),
                          'reasoning_max': max(rs)}
    d.close()
    print('-' * 70)
    p2 = out['2']['fails'] / out['2']['runs']
    p8 = out['8']['fails'] / out['8']['runs']
    print()
    print('доля отказов: группа 8 — %.0f%%, группа 2 — %.0f%%' % (100 * p8, 100 * p2))
    print()
    print('Что это значит для потери форм:')
    print('  страницы пропускаются только при отказе группы из 2 страниц,')
    print('  то есть примерно в %.0f%% случаев на каждую такую группу.' % (100 * p2))
    if p2 == 0:
        print('  на этой выборке группа из 2 страниц не провалилась ни разу:')
        print('  повтор вполовину, похоже, отказ вылечивает, и формы не теряются,')
        print('  но растёт число вызовов (отсюда задержка, а не потеря).')
    else:
        print('  то есть формы действительно теряются — это уже не про деньги.')
    json.dump(out, io.open(r'D:\models\_detect_groupsize_%s.json' % prof.name, 'w',
                           encoding='utf-8'), ensure_ascii=False, indent=1)
    print('токены: pt=%d ct=%d, стоимость %.4f ₽'
          % (P.USAGE['prompt'], P.USAGE['completion'], P.USAGE['cost_rub']))


if __name__ == '__main__':
    main()
