# -*- coding: utf-8 -*-
r"""Проверка регрессии: теряется ли ИНН/ОКПО титульного листа при правке 2.

Титульный лист читается как `transcripts['balance_p1']`. Новая подсказка детекции
называет страницу 1 категорией other (титул), значит ключа `balance_p1` не будет и
`company_from_title` вернёт пусто.
"""
import io, os, re, sys, json

sys.path.insert(0, r'D:\models')
import pipeline as P

PAGES = P.PAGESDIR
EX = r'D:\models\extracted'

for stem in ('Артген (ИСКЧ)_6мес_2025', 'Артген (ИСКЧ)_6мес_2026'):
    print('=' * 70)
    print(stem)
    old_f = os.path.join(PAGES, f'_llm_{stem}_detect.json')
    new_f = os.path.join(PAGES, f'_llm_{P.detect_cache_stem(stem + ".pdf")}.json')
    for lbl, f in (('старые метки', old_f), ('новые метки', new_f)):
        if not os.path.exists(f):
            print('  %s: нет файла' % lbl); continue
        pm = json.load(io.open(f, encoding='utf-8'))
        m = {p.get('page'): p.get('form') for p in pm if isinstance(p, dict)}
        print('  %s: стр.1=%r  стр.2=%r  стр.3=%r' % (lbl, m.get(1), m.get(2), m.get(3)))
        print('      страницы форм: %s'
              % {k: sorted(p for p, v in m.items() if v == k)
                 for k in P.FORM_LABELS if any(v == k for v in m.values())})
    ap = os.path.join(EX, stem + '.json')
    if os.path.exists(ap):
        d = json.load(io.open(ap, encoding='utf-8'))
        print('  в артефакте: company=%s' % json.dumps(d.get('company'), ensure_ascii=False))
        print('               unit=%s' % json.dumps(d.get('unit'), ensure_ascii=False))
        print('               balance transcript_pages=%s'
              % ((d.get('balance') or {}).get('transcript_pages')))
    # есть ли кэш транскрипта страницы 1 — и есть ли в нём ИНН
    for p in (1, 2):
        cp = P.page_cache_path(None, stem + '.pdf', p, 200, P.M_MAIN)
        if os.path.exists(cp):
            t = io.open(cp, encoding='utf-8', errors='replace').read()
            mm = re.search(r'ИНН[^0-9]{0,8}(\d{10,12})', t.replace('|', ' '))
            print('  транскрипт стр.%d: есть, ИНН=%s' % (p, mm.group(1) if mm else 'нет'))
        else:
            print('  транскрипт стр.%d: нет кэша' % p)
