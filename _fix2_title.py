# -*- coding: utf-8 -*-
r"""Проверка исправления: титульный лист читается и даёт ИНН/ОКПО/единицу.

Бесплатно: транскрипт страницы 1 уже в кэше (200 dpi, основная модель).
"""
import io, os, sys, json

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
SRC = r'D:\data-scraping\downloads'


def find_pdf(stem):
    for root, _, files in os.walk(SRC):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


for stem in ('Артген (ИСКЧ)_6мес_2025', 'Артген (ИСКЧ)_6мес_2026'):
    print('=' * 70)
    print(stem)
    path = find_pdf(stem)
    doc = P.pymupdf.open(path)
    name = os.path.basename(path)
    t1 = P.transcribe_cached(doc, 1, name, dpi=200, model=P.M_MAIN)
    doc.close()
    rq = P.company_from_title(t1)
    print('  company_from_title(титульный лист) -> %s' % json.dumps(rq, ensure_ascii=False))
    print('  ключ, под которым лист будет доступен: title_p1')
    art = os.path.join(EX, stem + '.json')
    if os.path.exists(art):
        d = json.load(io.open(art, encoding='utf-8'))
        print('  в артефакте было: company=%s unit=%s'
              % (json.dumps(d.get('company'), ensure_ascii=False),
                 json.dumps(d.get('unit'), ensure_ascii=False)))
    print('  СОВПАДАЕТ: %s' % (rq.get('okpo') == (d.get('company') or {}).get('okpo')
                              if os.path.exists(art) else 'н/д'))
print()
print('Титульный лист читается из того же кэша, что и раньше: новых трат нет.')
