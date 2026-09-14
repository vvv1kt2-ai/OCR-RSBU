# -*- coding: utf-8 -*-
r"""Сравнение качества детекции Polza и PlusVibe по нескольким прогонам.

Одного прогона мало: детекция шумит (кэш Polza и повтор Polza разошлись), поэтому
сравниваются распределения. Две метрики, обе про то, что важно на выходе:

  засорение — страница отнесена к форме, а на ней пояснения. Лишняя страница
              транскрибируется, а на эскалации её читает дорогая модель;
  пропуск   — страница с формой не отнесена к ней. Это потеря строк формы.

Истина берётся там, где она бесплатна: из уже оплаченных транскриптов страниц и из
текстового слоя PDF. Страницы, где истину установить нечем, в счёт не идут.
"""
import io, os, re, json, sys
from collections import Counter

sys.path.insert(0, r'D:\models')
import pipeline as P
import fitz

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
DL = r'D:\data-scraping\downloads'
MAIN_TAG = P.model_tag(P.M_MAIN)
TR = re.compile(r'^(.+)_p(\d+)_200_(.+?)_([0-9a-f]{10})\.md$')
FORMS = ('balance', 'income_statement', 'cash_flow')


def classify(txt):
    t = (txt or '').replace('\u00a0', ' ')
    if 'Пояснения к бухгалтерскому балансу' in t or 'Пояснения к балансу' in t:
        return 'notes'
    if '0710001' in t or 'Бухгалтерский баланс' in t:
        return 'balance'
    if '0710002' in t or 'финансовых результатах' in t:
        return 'income_statement'
    if '0710004' in t or '0710005' in t or 'движении денежных средств' in t:
        return 'cash_flow'
    return None


def truth_for(stem):
    """страница -> форма, по транскрипту или по текстовому слою"""
    out = {}
    pdf = os.path.join(DL, stem + '.pdf')
    # 1. транскрипты (уже оплачены)
    for fn in os.listdir(PAGES):
        m = TR.match(fn)
        if not m or m.group(1) != stem or m.group(3) != MAIN_TAG:
            continue
        c = classify(io.open(os.path.join(PAGES, fn), encoding='utf-8').read())
        if c:
            out[int(m.group(2))] = c
    # 2. текстовый слой — там, где транскрипта нет
    if os.path.exists(pdf):
        try:
            d = fitz.open(pdf)
            for i in range(d.page_count):
                p = i + 1
                if p in out:
                    continue
                t = d[i].get_text()
                if len(t) < 100:
                    continue
                c = classify(t)
                if c:
                    out[p] = c
            d.close()
        except Exception:
            pass
    return out


def load(name):
    p = os.path.join(r'D:\models', '_detect_%s.json' % name)
    if not os.path.exists(p):
        return None
    return json.load(io.open(p, encoding='utf-8'))


def metrics(entry, truth):
    """(засорение, пропуск) для одного прогона"""
    contam, missed = [], []
    for form, pages in entry['by_form'].items():
        if form not in FORMS:
            continue
        for p in pages:
            if truth.get(p) == 'notes':
                contam.append((form, p))
    for p, t in truth.items():
        if t in FORMS:
            got = [f for f in FORMS if p in (entry['by_form'].get(f) or [])]
            if t not in got:
                missed.append((t, p))
    return contam, missed


def main():
    polza, pv = load('polza'), load('plusvibe')
    if not polza or not pv:
        sys.exit('нет файлов прогонов: polza=%s plusvibe=%s'
                 % (bool(polza), bool(pv)))
    docs = sorted(set(polza) & set(pv))
    print('документов, посчитанных обоими: %d' % len(docs))
    print()

    summary = {'polza': {'contam': [], 'missed': []},
               'plusvibe': {'contam': [], 'missed': []}}
    detail = []
    for stem in docs:
        truth = truth_for(stem)
        n_notes = sum(1 for v in truth.values() if v == 'notes')
        n_forms = sum(1 for v in truth.values() if v in FORMS)
        for name, data in (('polza', polza), ('plusvibe', pv)):
            for run in data[stem]['runs']:
                c, m = metrics(run, truth)
                summary[name]['contam'].append(len(c))
                summary[name]['missed'].append(len(m))
        detail.append({'stem': stem, 'npages': polza[stem]['npages'],
                       'truth_notes': n_notes, 'truth_forms': n_forms,
                       'runs': {'polza': len(polza[stem]['runs']),
                                'plusvibe': len(pv[stem]['runs'])},
                       'balance': {'polza': [r['by_form'].get('balance')
                                             for r in polza[stem]['runs']],
                                   'plusvibe': [r['by_form'].get('balance')
                                                for r in pv[stem]['runs']]}})

    print('=== засорение: страницы пояснений, отнесённые к форме ===')
    print('%-34s %6s %8s %22s %22s'
          % ('документ', 'стр.', 'поясн.', 'Polza', 'PlusVibe'))
    print('-' * 96)
    for d in detail:
        stem = d['stem']
        t = truth_for(stem)
        pc = [len(metrics(r, t)[0]) for r in polza[stem]['runs']]
        vc = [len(metrics(r, t)[0]) for r in pv[stem]['runs']]
        fp = ('%g %s' % (sum(pc) / len(pc), pc)) if pc else 'нет прогонов'
        fv = ('%g %s' % (sum(vc) / len(vc), vc)) if vc else 'нет прогонов'
        print('%-34s %6d %8d %22s %22s'
              % (stem[:34], d['npages'], d['truth_notes'], fp, fv))
    print('-' * 96)

    print()
    print('=== сводка по %d документам и %d прогонам ===' % (
        len(docs), len(summary['polza']['contam'])))
    for name in ('polza', 'plusvibe'):
        c = summary[name]['contam']
        m = summary[name]['missed']
        if not c:
            print('%-10s нет прогонов' % name)
            continue
        print('%-10s засорение: всего %d, на прогон в среднем %.1f (мин %d, макс %d)'
              % (name, sum(c), sum(c) / len(c), min(c), max(c)))
        print('%-10s пропуск:   всего %d, на прогон в среднем %.1f (мин %d, макс %d)'
              % ('', sum(m), sum(m) / len(m), min(m), max(m)))

    print()
    print('=== устойчивость: насколько список баланса гуляет между прогонами ===')
    for name, data in (('polza', polza), ('plusvibe', pv)):
        var = []
        for stem in docs:
            sets = [set(r['by_form'].get('balance') or []) for r in data[stem]['runs']]
            if len(sets) > 1:
                union = set().union(*sets)
                inter = set.intersection(*sets)
                var.append(len(union) - len(inter))
        if var:
            print('%-10s разброс размера списка баланса: в среднем %.1f стр., макс %d'
                  % (name, sum(var) / len(var), max(var)))

    json.dump({'detail': detail, 'summary': summary},
              io.open(r'D:\models\_detect_cmp.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print()
    print('-> _detect_cmp.json')


if __name__ == '__main__':
    main()
