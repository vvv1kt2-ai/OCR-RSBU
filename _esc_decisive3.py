# -*- coding: utf-8 -*-
r"""Проверка теста А: 200 dpi прочитал строку с ОШИБКОЙ или не прочитал её вовсе?

Если старое (ошибочное) значение находится в тексте 200 dpi, значит 200 dpi прочитал
строку, но с ошибкой — и 300 dpi действительно её исправил.
Если не находится — значит строка на 200 dpi не читалась, и вывод иной.
"""
import io, os, re

PAGES = r'D:\models\extracted\pages'
CACHE = re.compile(r'^(?P<stem>.+)_p(?P<p>\d+)_(?P<dpi>\d+)_(?P<rest>.+)\.md$')

CASES = [
    ('Славянск ЭКО_6мес_2025', 2, '92891824', '92891924', '1100 кол.1'),
    ('Славянск ЭКО_6мес_2025', 2, '2942100', None, '1240 кол.2 (было пусто)'),
    ('ТГК-14_6мес_2025', 3, '11081647', '11061647', '1250 кол.0'),
]


def norm(t):
    return re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', t or '')


files = {}
for f in os.listdir(PAGES):
    m = CACHE.match(f)
    if m:
        files.setdefault((m.group('stem'), int(m.group('p')), int(m.group('dpi'))), f)

for stem, p, old, new, what in CASES:
    print('=== %s, стр.%d, %s' % (stem, p, what))
    for dpi in (200, 300):
        f = files.get((stem, p, dpi))
        if not f:
            print('  %d dpi: транскрипта нет' % dpi)
            continue
        t = norm(io.open(os.path.join(PAGES, f), encoding='utf-8').read())
        print('  %d dpi (%d знаков):' % (dpi, len(t)))
        print('      ошибочное %s: %s' % (old, 'НАЙДЕНО' if old in t else 'нет'))
        if new:
            print('      верное    %s: %s' % (new, 'НАЙДЕНО' if new in t else 'нет'))
        # покажу строку вокруг ошибочного числа, если оно есть
        i = t.find(old)
        if i >= 0:
            print('      контекст: ...%s...' % t[max(0, i - 60):i + 20].replace('\n', ' '))
    print()
