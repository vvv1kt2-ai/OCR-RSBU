# -*- coding: utf-8 -*-
r"""Разбор сохранённых страниц: вытащить текст и найти цены.

Страницы — это сохранённый HTML (400-600 КБ каждая, почти всё разметка). Полный текст
складывается рядом в `_текст\<имя>.txt`, а на экран идёт только сводка: сколько текста
получилось и строки, где речь о деньгах.
"""
import io, os, re, sys

from bs4 import BeautifulSoup

SRC = r'D:\models\информация'
DST = os.path.join(SRC, '_текст')
os.makedirs(DST, exist_ok=True)

MONEY = re.compile(r'(₽|руб|цена|стоимост|тариф|за\s+1\s*(?:млн|тыс)|1000\s*(?:страниц|единиц)|'
                   r'OCR|Vision|страниц)', re.I)

files = [f for f in os.listdir(SRC) if f.lower().endswith(('.html', '.htm'))]
print('страниц найдено: %d' % len(files))
print()

for fn in sorted(files):
    path = os.path.join(SRC, fn)
    html = io.open(path, encoding='utf-8', errors='replace').read()
    soup = BeautifulSoup(html, 'lxml')
    for t in soup(['script', 'style', 'noscript']):
        t.decompose()
    text = soup.get_text('\n')
    lines = [re.sub(r'\s+', ' ', l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    out = os.path.join(DST, os.path.splitext(fn)[0][:70] + '.txt')
    io.open(out, 'w', encoding='utf-8').write('\n'.join(lines))

    money = [l for l in lines if MONEY.search(l) and len(l) < 220]
    print('%-64s %7d строк, %8d знаков, упоминаний денег/OCR %d'
          % (fn[:64], len(lines), sum(len(l) for l in lines), len(money)))

print()
print('текст сохранён в: %s' % DST)
