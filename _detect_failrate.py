# -*- coding: utf-8 -*-
r"""Доля отказов детекции: сколько вызовов из N возвращаются без текста.

Отказ перемежающийся, поэтому одного вызова мало. Причина отказа известна из ответа
поставщика: «весь заданный вами max_tokens ушёл на внутренние рассуждения модели».
Здесь измеряется частота, а не факт.

Запуск:  $env:PILOT_PROVIDER='plusvibe'; python _detect_failrate.py --n 15
         $env:PILOT_PROVIDER='polza';    python _detect_failrate.py --n 15
"""
import io, json, os, sys, time, urllib.request, statistics

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR
import fitz

DOCS = ['Сибсульфур_6мес_2026', 'Моторные технологии_6мес_2025']
GROUP_SIZE = 8
DL = r'D:\data-scraping\downloads'


def one_call(doc_obj, group, npages, prof, key, max_tokens=1200):
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
                'chars': len(txt),
                'parsed': len(P.salvage_pages_map(txt, npages))}
    except urllib.error.HTTPError as e:
        raw = e.read()[:500].decode('utf-8', 'replace')
        try:
            msg = json.loads(raw).get('error', {}).get('message', '')
        except Exception:
            msg = raw
        return {'ok': False, 'code': e.code, 'msg': msg[:200]}
    except Exception as e:
        return {'ok': False, 'code': '?', 'msg': str(e)[:200]}


def main():
    n = 15
    if '--n' in sys.argv:
        n = int(sys.argv[sys.argv.index('--n') + 1])
    prof = PR.active()
    key = PR.load_key(prof)
    out = os.path.join(r'D:\models', '_detect_failrate_%s.json' % prof.name)
    print('поставщик: %s, модель детекции len=%d' % (prof.name, len(P.M_DETECT)))
    print('документов: %d, повторов на группу: %d, предел ответа: 1200' % (len(DOCS), n))
    print()

    res = {}
    for stem in DOCS:
        pdf = os.path.join(DL, stem + '.pdf')
        if not os.path.exists(pdf):
            continue
        d = fitz.open(pdf)
        npages = d.page_count
        group = list(range(1, min(GROUP_SIZE, npages) + 1))
        runs = []
        print('%s (страниц %d, группа %s)' % (stem, npages, group))
        for i in range(n):
            r = one_call(d, group, npages, prof, key)
            runs.append(r)
            mark = 'ok' if r['ok'] else 'ОТКАЗ %s' % r['code']
            extra = ('ct=%d рассужд=%d знаков=%d страниц=%d'
                     % (r['ct'], r['reasoning'], r['chars'], r['parsed'])) if r['ok'] else r['msg'][:70]
            print('  %2d/%d %-12s %s' % (i + 1, n, mark, extra))
        d.close()
        res[stem] = runs

    print()
    print('=== итог по поставщику %s ===' % prof.name)
    allruns = [r for v in res.values() for r in v]
    fails = [r for r in allruns if not r['ok']]
    print('вызовов: %d, отказов: %d (%.0f%%)'
          % (len(allruns), len(fails), 100 * len(fails) / max(len(allruns), 1)))
    oks = [r for r in allruns if r['ok']]
    if oks:
        rs = [r['reasoning'] for r in oks]
        print('рассуждения в удачных вызовах: медиана %d, максимум %d'
              % (statistics.median(rs), max(rs)))
        print('страниц разобрано в удачных: медиана %d из %d'
              % (statistics.median([r['parsed'] for r in oks]), GROUP_SIZE))
        print('пустых разборов (0 страниц): %d из %d'
              % (sum(1 for r in oks if r['parsed'] == 0), len(oks)))
    for r in fails:
        print('  отказ HTTP %s: %s' % (r['code'], r['msg'][:120]))
    json.dump(res, io.open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('-> %s' % out)
    print('токены: pt=%d ct=%d, стоимость %.4f ₽'
          % (P.USAGE['prompt'], P.USAGE['completion'], P.USAGE['cost_rub']))


if __name__ == '__main__':
    main()
