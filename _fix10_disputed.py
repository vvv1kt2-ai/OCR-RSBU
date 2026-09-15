# -*- coding: utf-8 -*-
r"""Проверка спорных страниц: настоящие ли это продолжения баланса.

Постраничная детекция находила баланс то на [2,3,22], то на [2,3,24]. Прежде чем
считать эти страницы лишними (и говорить о перерасходе) или нужными (и говорить о
спасённых данных), надо посмотреть, что на них есть. Читаем их и смотрим признаки формы.
"""
import io, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

STEM = 'НовосибирскАвтодор_6мес_2025.pdf'
PAGES = [22, 24, 1, 49]
path = os.path.join(P.DOWNLOADS, STEM)
doc = P.pymupdf.open(path)
print('документ: %s, страниц %d' % (STEM, len(doc)))
print()
cost0 = P.USAGE['cost_rub']
rows = []
for p in PAGES:
    page = doc[p - 1]
    txt_layer = page.get_text().strip()
    nimg = len(page.get_images(full=True))
    txt = P.transcribe_cached(doc, p, STEM, dpi=200, model=P.M_MAIN)
    low = txt.lower()
    if 'бухгалтерский баланс' in low:
        head = 'Бухгалтерский баланс'
    elif 'финансовых результатах' in low:
        head = 'Отчет о фин. результатах'
    elif 'движении денежных средств' in low:
        head = 'Отчет о движении ден. ср.'
    elif 'пояснени' in low:
        head = 'Пояснения'
    else:
        head = '—'
    codes = sorted(set(re.findall(r'\b(1[1-7]\d0|2[4-5]\d0|4[1-5]\d0)\b', txt)))
    term = [c for c in ('1700', '2410', '2400', '4500') if re.search(r'\b%s\b' % c, txt)]
    rows.append((p, len(txt), head, term, codes, len(txt_layer), nimg))
doc.close()

print('%4s %9s %-26s %-14s %6s %6s %5s' %
      ('стр.', 'знаков', 'заголовок', 'итоговый код', 'кодов', 'текст', 'карт.'))
for p, n, head, term, codes, tl, nimg in rows:
    print('%4d %9d %-26s %-14s %6d %6d %5d'
          % (p, n, head, ','.join(term) or '—', len(codes), tl, nimg))
print()
print('коды строк по страницам:')
for p, n, head, term, codes, tl, nimg in rows:
    print('  стр. %2d: %s' % (p, ', '.join(codes) if codes else 'нет'))
print()
print('цена проверки: %.3f ₽' % (P.USAGE['cost_rub'] - cost0))
print()
print('Читать так: страница-продолжение баланса несёт коды строк 11xx-17xx,')
print('а титул и текстовые страницы — ни одного.')
