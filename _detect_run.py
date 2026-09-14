# -*- coding: utf-8 -*-
r"""Повтор детекции активным профилем, несколько раз: те же страницы, тот же промпт.

Детекция — шумный процесс: один и тот же документ у одного и того же поставщика
размечается по-разному от запуска к запуску (проверено: кэш Polza и повтор Polza
разошлись). Поэтому качество сравнивается по нескольким прогонам, а не по одному.

Логика повторена по `pipeline.scan_pipeline` (строки 885-927) с его же константами:
DETECT_PROMPT, M_DETECT, render_png, img_parts, salvage_pages_map, шаг 8.

Запуск:  $env:PILOT_PROVIDER='plusvibe'; python _detect_run.py --repeat 3
Пишет _detect_<профиль>.json. Уже сделанные прогоны не повторяются.
"""
import io, os, re, json, sys, time

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
DL = r'D:\data-scraping\downloads'
CH = 8


def detect(doc, npages):
    """детекция страниц: один вызов на документ до 10 страниц, дальше группами по 8"""
    pages_map = []
    cand = list(range(1, npages + 1))
    if len(cand) <= 10:
        msgs = [{'role': 'user', 'content': [{'type': 'text', 'text': P.DETECT_PROMPT}]}]
        for i in cand:
            msgs[0]['content'].extend(
                P.img_parts(P.render_png(doc[i - 1], 120), f'СТРАНИЦА {i}'))
        txt, _ = P.chat(msgs, P.M_DETECT, temperature=0, max_tokens=4000)
        try:
            pm = P.extract_json(txt).get('pages', [])
        except ValueError:
            pm = P.salvage_pages_map(txt, npages)
        return pm or P.salvage_pages_map(txt, npages)

    def group(g):
        cm = [{'role': 'user', 'content': [
            {'type': 'text',
             'text': P.DETECT_PROMPT + f' (Страницы {g[0]}-{g[-1]} из {npages})'}]}]
        for j in g:
            cm[0]['content'].extend(
                P.img_parts(P.render_png(doc[j - 1], 120), f'СТРАНИЦА {j}'))
        txt, _ = P.chat(cm, P.M_DETECT, temperature=0, max_tokens=1200)
        pm = P.salvage_pages_map(txt, npages)
        if not pm:
            try:
                pm = P.extract_json(txt).get('pages', [])
            except ValueError:
                pm = []
        pages_map.extend(pm)

    for lo in range(0, len(cand), CH):
        group(cand[lo:lo + CH])
    return pages_map


def by_form(pm):
    out = {}
    for e in pm:
        if isinstance(e.get('page'), int) and isinstance(e.get('form'), str):
            out.setdefault(e['form'], []).append(e['page'])
    return {k: sorted(set(v)) for k, v in out.items()}


def main():
    import fitz
    prof = PR.active()
    out = os.path.join(r'D:\models', '_detect_%s.json' % prof.name)
    repeat = 1
    if '--repeat' in sys.argv:
        repeat = int(sys.argv[sys.argv.index('--repeat') + 1])
    only = None
    if '--docs' in sys.argv:
        only = sys.argv[sys.argv.index('--docs') + 1].split('|')

    cached = sorted(f[len('_llm_'):-len('_detect.json')] for f in os.listdir(PAGES)
                    if f.startswith('_llm_') and f.endswith('_detect.json')
                    and '_pv' not in f)
    if only:
        cached = [c for c in cached if c in only]
    print('профиль: %s, модель детекции len=%d' % (prof.name, len(P.M_DETECT)))
    print('документов: %d, повторов на документ: %d' % (len(cached), repeat))
    print()

    res = {}
    if os.path.exists(out):
        res = json.load(io.open(out, encoding='utf-8'))
        print('уже посчитано ранее: %d документов' % len(res))

    t0 = time.time()
    for stem in cached:
        pdf = os.path.join(DL, stem + '.pdf')
        if not os.path.exists(pdf):
            print('  %-34s нет PDF' % stem[:34])
            continue
        ent = res.setdefault(stem, {'npages': None, 'runs': []})
        d = fitz.open(pdf)
        ent['npages'] = d.page_count
        try:
            while len(ent['runs']) < repeat:
                k = len(ent['runs']) + 1
                try:
                    pm = detect(d, d.page_count)
                except Exception as e:
                    print('  %-34s прогон %d ОШИБКА %s' % (stem[:34], k, str(e)[:50]))
                    break
                ent['runs'].append({'by_form': by_form(pm), 'n': len(pm)})
                json.dump(res, io.open(out, 'w', encoding='utf-8'),
                          ensure_ascii=False, indent=1)
        finally:
            d.close()
        bf = ent['runs'][-1]['by_form'] if ent['runs'] else {}
        print('  %-34s стр.%-3d прогонов %d, balance=%s'
              % (stem[:34], ent['npages'], len(ent['runs']), bf.get('balance')))

    json.dump(res, io.open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print()
    print('время: %.0f с' % (time.time() - t0))
    print('токены: pt=%d ct=%d, стоимость %.4f ₽'
          % (P.USAGE['prompt'], P.USAGE['completion'], P.USAGE['cost_rub']))
    print('-> %s' % out)


if __name__ == '__main__':
    main()
