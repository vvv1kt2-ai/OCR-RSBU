# -*- coding: utf-8 -*-
r"""Уточнение: 1200 против 4000 на документе, где отказы идут, с большой выборкой.

Первый замер дал 19% отказов при 1200, 0% при 4000 и 12% при 8000 — при том что
рассуждения везде были ниже предела. Значит либо порог не при чём, либо выборки по 16
мало, чтобы различить 0% и 12%. Здесь берётся один документ и по 25 вызовов на предел.
"""
import io, json, os, sys, urllib.request, statistics

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR
import fitz

DL = r'D:\data-scraping\downloads'
DOC = 'Моторные технологии_6мес_2025'
GROUP = 8


def call(doc_obj, group, npages, prof, key, max_tokens):
    cm = [{'role': 'user', 'content': [
        {'type': 'text',
         'text': P.DETECT_PROMPT + f' (Страницы {group[0]}-{group[-1]} из {npages})'}]}]
    for j in group:
        cm[0]['content'].extend(
            P.img_parts(P.render_png(doc_obj[j - 1], 120), f'СТРАНИЦА {j}'))
    url, headers, body = PR.build_request(prof, P.M_DETECT, cm, key,
                                          temperature=0, max_tokens=max_tokens)
    req = urllib.request.Request(url, data=body, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.loads(r.read())
        u = resp.get('usage') or {}
        det = u.get('completion_tokens_details') or {}
        txt = resp['choices'][0]['message']['content'] or ''
        return {'ok': True, 'ct': u.get('completion_tokens') or 0,
                'reasoning': det.get('reasoning_tokens') or 0,
                'parsed': len(P.salvage_pages_map(txt, npages))}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'code': e.code}
    except Exception:
        return {'ok': False, 'code': '?'}


def main():
    n = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 25
    prof = PR.active()
    key = PR.load_key(prof)
    pdf = os.path.join(DL, DOC + '.pdf')
    d = fitz.open(pdf)
    npages = d.page_count
    g = list(range(1, min(GROUP, npages) + 1))
    print('поставщик: %s, документ: %s (страниц %d)' % (prof.name, DOC, npages))
    print('группа %s, вызовов на предел: %d' % (g, n))
    print()
    print('%-8s %8s %8s %10s %14s %16s'
          % ('предел', 'вызовов', 'отказов', 'доля', 'рассужд медиана', 'рассужд макс'))
    print('-' * 72)
    out = {}
    for mt in (1200, 4000):
        runs = []
        for i in range(n):
            runs.append(call(d, g, npages, prof, key, mt))
        fails = [r for r in runs if not r['ok']]
        oks = [r for r in runs if r['ok']]
        rs = [r['reasoning'] for r in oks] or [0]
        print('%-8d %8d %8d %9.0f%% %14d %16d'
              % (mt, len(runs), len(fails), 100 * len(fails) / len(runs),
                 statistics.median(rs), max(rs)))
        out[str(mt)] = {'runs': len(runs), 'fails': len(fails),
                        'reasoning_median': statistics.median(rs),
                        'reasoning_max': max(rs),
                        'parsed_median': statistics.median([r['parsed'] for r in oks] or [0])}
    d.close()
    print('-' * 72)
    # различие значимо, если доли не пересекаются по грубой оценке
    a, b = out['1200'], out['4000']
    print()
    print('1200: отказов %d из %d (%.0f%%)' % (a['fails'], a['runs'],
                                               100 * a['fails'] / a['runs']))
    print('4000: отказов %d из %d (%.0f%%)' % (b['fails'], b['runs'],
                                               100 * b['fails'] / b['runs']))
    if a['fails'] and not b['fails']:
        print('вывод: подъём предела убирает отказы на этой выборке')
    elif a['fails'] and b['fails']:
        print('вывод: подъём предела отказы НЕ убирает — нужен повтор')
    else:
        print('вывод: отказов нет ни там ни там')
    json.dump(out, io.open(r'D:\models\_detect_maxtok2_%s.json' % prof.name, 'w',
                           encoding='utf-8'), ensure_ascii=False, indent=1)
    print('токены: pt=%d ct=%d, стоимость %.4f ₽'
          % (P.USAGE['prompt'], P.USAGE['completion'], P.USAGE['cost_rub']))


if __name__ == '__main__':
    main()
