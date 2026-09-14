# -*- coding: utf-8 -*-
r"""Каким должен быть предел ответа у детекции, чтобы отказы прекратились.

`reasoning_effort=none` у модели детекции не действует (проверено: рассуждения
остаются). Причина отказа — рассуждения не помещаются в max_tokens=1200, который
конвейер задаёт для групп по 8 страниц. Значит лечится пределом.

Здесь измеряется доля отказов при разных пределах. Стоит копейки.
"""
import io, json, os, sys, urllib.request, statistics

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR
import fitz

DL = r'D:\data-scraping\downloads'
DOCS = ['Моторные технологии_6мес_2025', 'Сибсульфур_6мес_2026']
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
    except Exception as e:
        return {'ok': False, 'code': '?'}


def main():
    n = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 8
    prof = PR.active()
    key = PR.load_key(prof)
    print('поставщик: %s' % prof.name)
    print('группа из %d страниц, повторов на предел: %d' % (GROUP, n))
    print()
    print('%-10s %10s %10s %12s %12s %10s'
          % ('предел', 'вызовов', 'отказов', 'доля', 'рассужд медиана', 'страниц'))
    print('-' * 72)
    out = {}
    for mt in (1200, 2000, 4000, 8000):
        runs = []
        for stem in DOCS:
            pdf = os.path.join(DL, stem + '.pdf')
            if not os.path.exists(pdf):
                continue
            d = fitz.open(pdf)
            g = list(range(1, min(GROUP, d.page_count) + 1))
            for _ in range(n):
                runs.append(call(d, g, d.page_count, prof, key, mt))
            d.close()
        fails = [r for r in runs if not r['ok']]
        oks = [r for r in runs if r['ok']]
        rs = [r['reasoning'] for r in oks] or [0]
        ps = [r['parsed'] for r in oks] or [0]
        print('%-10d %10d %10d %11.0f%% %12d %10.1f'
              % (mt, len(runs), len(fails), 100 * len(fails) / len(runs),
                 statistics.median(rs), statistics.median(ps)))
        out[str(mt)] = {'runs': len(runs), 'fails': len(fails),
                        'reasoning_median': statistics.median(rs),
                        'parsed_median': statistics.median(ps),
                        'reasoning_max': max(rs)}
    print('-' * 72)
    print()
    for mt, v in out.items():
        print('  предел %-5s отказов %2d из %2d, рассуждения макс %d'
              % (mt, v['fails'], v['runs'], v['reasoning_max']))
    json.dump(out, io.open(r'D:\models\_detect_maxtok_%s.json' % prof.name, 'w',
                           encoding='utf-8'), ensure_ascii=False, indent=1)
    print()
    print('токены: pt=%d ct=%d, стоимость %.4f ₽'
          % (P.USAGE['prompt'], P.USAGE['completion'], P.USAGE['cost_rub']))


if __name__ == '__main__':
    main()
