# -*- coding: utf-8 -*-
r"""Почему ИПС_6мес_2026 в этом прогоне пошёл по текстовой ветке и остался ни с чем.

Гипотезы:
  A) текстовый слой есть, но в нём нет ни шапки формы, ни кодов строк — тогда find_form_pages
     честно ничего не находит, и дефект не наш, а следствие испорченного слоя;
  B) слой хороший, но разбор его не видит — тогда это наш дефект.

Проверяем без вызовов: печатаем, что именно лежит в текстовом слое (шапки, коды строк,
доля латиницы — признак битого OCR).
"""
import io, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

STEM = 'ИПС_6мес_2026'


def find_pdf(stem):
    for root, _, files in os.walk(P.DOWNLOADS):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


doc = P.pymupdf.open(find_pdf(STEM))
n = len(doc)
print('%s: страниц %d' % (STEM, n))
chars = sum(len(p.get_text().strip()) for p in doc)
print('знаков в слое всего: %d -> has_text=%s (порог 200)' % (chars, chars > 200))
garbled = [p for p in range(1, n + 1) if P._garbled_page(doc[p - 1])]
print('страниц с битым OCR: %d из %d (условие скана: >= max(2, %d))'
      % (len(garbled), n, n // 4))
print()
print('%-5s %7s %8s %8s %8s %s' % ('стр.', 'знаков', 'латиниц', 'кодов', 'шапка', 'первые слова'))
CODE = re.compile(r'\b(1[1-7]\d0|2[1-4]\d0|4[1-5]\d0)\b')
for p in range(1, n + 1):
    t = doc[p - 1].get_text()
    lat = len(re.findall(r'[A-Za-z]', t))
    codes = sorted(set(CODE.findall(t)))
    head = 'да' if re.search(r'Бухгалтерский баланс|Форма\s*0710', t) else '—'
    first = ' '.join(t.split())[:60]
    print('%-5d %7d %8d %8d %8s %s' % (p, len(t.strip()), lat, len(codes), head, first))
print()
found = P.find_form_pages(doc)
print('find_form_pages вернул: %s' % {k: list(v) for k, v in found.items()})
doc.close()
