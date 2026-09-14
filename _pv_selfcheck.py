# -*- coding: utf-8 -*-
"""Самосогласованность: поставщик против самого себя на той же странице.

Сравнение с эталоном Polza меряет разницу двух моделей, а не дефект одной из них.
Если Polza на повторном прогоне теряет столько же строк, сколько PlusVibe, то
«выпавшие строки» — разброс модели, а не свойство поставщика.

Каждый поставщик вызывается ЗАНОВО (кэш не читается, результат кладётся рядом),
поэтому опыт стоит денег: Polza — примерно 1.4 ₽ за страницу, PlusVibe — 0.18 ₽.

    python _pv_selfcheck.py --n 6
"""
import io, os, sys, json, time, argparse, hashlib
from collections import Counter

sys.path.insert(0, r'D:\models')
sys.path.insert(0, r'D:\models\pylibs')
import pipeline as P
import pymupdf
import _pv_quality as Q

R2 = os.path.join(Q.CACHE, '_r2')


def call_provider(base, key, model, messages, max_tokens=16000, timeout=300):
    import urllib.request
    body = json.dumps({'model': model, 'messages': messages,
                       'temperature': 0.1, 'max_tokens': max_tokens}).encode()
    req = urllib.request.Request(base, data=body, method='POST', headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    u = data.get('usage') or {}
    return (data['choices'][0]['message']['content'] or '',
            u.get('prompt_tokens', 0), u.get('completion_tokens', 0),
            data['choices'][0].get('finish_reason'))


def polza_key():
    import re
    txt = io.open(P.CRED, encoding='utf-8').read()
    return re.search(r'POLZA_API_KEY:\s*(\S+)', txt).group(1)


def compare(a, b):
    """что потерялось и что добавилось во втором ответе относительно первого"""
    d = Q.digit_diff(a, b)
    return len(d['absent']), len(d['undercount']), len(d['extra'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=6)
    ap.add_argument('--variant', default='default')
    ap.add_argument('--pages', default=None, help='документ:страница через запятую')
    args = ap.parse_args()
    os.makedirs(R2, exist_ok=True)

    mtag = P.model_tag(P.M_MAIN)
    if args.pages:
        pool = {(p['stem'], p['page']): p for p in Q.cached_pages(10 ** 6, want_tag=mtag)}
        pages = []
        for spec in args.pages.split(','):
            stem, _, pg = spec.strip().rpartition(':')
            pages.append(pool[(stem, int(pg))])
    else:
        pages = Q.cached_pages(args.n, want_tag=mtag)

    pk = polza_key()
    pv_addr = Q.address(P.M_MAIN, args.variant)
    pvk = Q.key()
    print('страниц: %d' % len(pages))

    rows = []
    for r in pages:
        doc = pymupdf.open(r['pdf'])
        if r['page'] > len(doc):
            continue
        msg = [P.img_message(P.render_png(doc[r['page'] - 1], r['dpi']),
                             P.TRANSCRIBE_PROMPT + f' (страница {r["page"]} файла)')]
        tag = f'{r["stem"]}_p{r["page"]}_{r["dpi"]}'
        p1 = io.open(r['path'], encoding='utf-8').read()

        # Polza заново
        fp2 = os.path.join(R2, f'polza_{tag}.md')
        if os.path.exists(fp2):
            p2 = io.open(fp2, encoding='utf-8').read()
            pfin, pct = 'кэш', 0
        else:
            p2, ppt, pct, pfin = call_provider(P.BASE, pk, P.M_MAIN, msg)
            io.open(fp2, 'w', encoding='utf-8').write(p2)
        # PlusVibe заново
        fv2 = os.path.join(R2, f'pv_{tag}.md')
        if os.path.exists(fv2):
            v2 = io.open(fv2, encoding='utf-8').read()
            vfin, vct = 'кэш', 0
        else:
            v2, vpt, vct, vfin = call_provider(Q.BASE, pvk, pv_addr, msg)
            io.open(fv2, 'w', encoding='utf-8').write(v2)

        v1 = io.open(os.path.join(Q.CACHE, f'{tag}_{args.variant}_{mtag}.md'),
                     encoding='utf-8').read()

        pa, pu, pe = compare(p1, p2)      # Polza против Polza
        va, vu, ve = compare(v1, v2)      # PlusVibe против PlusVibe
        pc, _, _ = compare(p1, v1)        # Polza против PlusVibe (первый прогон)
        rows.append({'stem': r['stem'], 'page': r['page'],
                     'polza_self_absent': pa, 'polza_self_under': pu,
                     'pv_self_absent': va, 'pv_self_under': vu,
                     'cross_absent': pc, 'pfin': pfin, 'vfin': vfin,
                     'p_ct': pct, 'v_ct': vct})
        print('%-28s стр.%-3d | Polza сам с собой: нет %2d, реже %2d | '
              'PlusVibe сам с собой: нет %2d, реже %2d | между ними: нет %2d'
              % (r['stem'][:28], r['page'], pa, pu, va, vu, pc))

    cost = sum(r['p_ct'] for r in rows) / 1e6 * 229.0575 + \
           sum(r['v_ct'] for r in rows) / 1e6 * 18.86
    lines = ['# Самосогласованность поставщиков', '',
             'Повторный вызов той же модели тем же промптом на той же странице.',
             'Если повтор расходится так же сильно, как сравнение с другим поставщиком,',
             'то расхождение — разброс модели, а не дефект поставщика.', '',
             '| документ | стр. | Polza сам с собой: нет / реже | PlusVibe сам с собой: нет / реже | '
             'Polza против PlusVibe: нет |', '|---|---|---|---|---|']
    for r in rows:
        lines.append('| %s | %d | %d / %d | %d / %d | %d |'
                     % (r['stem'], r['page'], r['polza_self_absent'], r['polza_self_under'],
                        r['pv_self_absent'], r['pv_self_under'], r['cross_absent']))
    tot_p = sum(r['polza_self_absent'] + r['polza_self_under'] for r in rows)
    tot_v = sum(r['pv_self_absent'] + r['pv_self_under'] for r in rows)
    tot_c = sum(r['cross_absent'] for r in rows)
    lines += ['', '## Итог', '',
              '- Polza на повторе разошёлся сам с собой: %d расхождений' % tot_p,
              '- PlusVibe на повторе разошёлся сам с собой: %d расхождений' % tot_v,
              '- между поставщиками (первый прогон): %d пропавших чисел' % tot_c,
              '- потрачено: %.2f ₽' % cost, '',
              'Вывод: ' + ('расхождение между поставщиками не превышает собственного разброса '
                           'модели — сравнивать транскрипты бессмысленно, решать надо по '
                           'извлечённым значениям'
                           if tot_c <= max(tot_p, tot_v) * 1.5 else
                           'расхождение между поставщиками БОЛЬШЕ собственного разброса модели — '
                           'это свойство поставщика, а не шум')]
    io.open(r'D:\models\_pv_selfcheck.md', 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    json.dump(rows, io.open(r'D:\models\_pv_selfcheck.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n'.join(lines[-8:]))
    print('отчёт: _pv_selfcheck.md')


if __name__ == '__main__':
    main()
