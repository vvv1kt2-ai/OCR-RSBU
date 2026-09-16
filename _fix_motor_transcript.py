# -*- coding: utf-8 -*-
r"""Сверка «Моторные технологии_6мес_2025» с ТРАНСКРИПТОМ страницы баланса.

Правило проекта: дефект подтверждать доказательством — сверкой с напечатанным на странице,
а не рассуждением. Надо увидеть своими глазами, какие числа стоят в разделе II по колонке
«На 30 июня 2025 г.» (457, 200346, 4070, 467, 459962?) и нет ли на странице строки, которую
конвейер пропустил (остаток +14500 по колонке 0 и +87800 по колонке 1).

Ищем в кэше страниц этого документа строки с кодами раздела II и печатаем ОКРЕСТНОСТЬ
(немного строк вокруг), а не весь файл.
"""
import io, os, re, glob

PAGES = r'D:\models\extracted\pages'
STEM = 'Моторные технологии_6мес_2025'

files = sorted(glob.glob(os.path.join(PAGES, STEM + '_p*.md')))
print('транскриптов найдено: %d' % len(files))
for f in files:
    print('   %s  (%d байт)' % (os.path.basename(f), os.path.getsize(f)))

WANT = ['1200', '1210', '1215', '1220', '1230', '1240', '1250', '1260']
print()
for f in files:
    try:
        txt = io.open(f, encoding='utf-8', errors='replace').read()
    except Exception as e:
        print('%s: не прочитать (%s)' % (os.path.basename(f), e))
        continue
    lines = txt.splitlines()
    hits = [i for i, ln in enumerate(lines) if any(re.search(r'(?<!\d)%s(?!\d)' % c, ln) for c in WANT)]
    # страница интересна, если в ней есть 1200 или несколько кодов раздела II
    if not hits or len(hits) < 3:
        continue
    print('=' * 96)
    print('ФАЙЛ: %s   (совпадений %d)' % (os.path.basename(f), len(hits)))
    lo, hi = max(0, min(hits) - 3), min(len(lines), max(hits) + 4)
    for i in range(lo, hi):
        ln = lines[i].rstrip()
        mark = ' <=' if i in hits else ''
        print('%4d | %s%s' % (i + 1, ln[:150], mark))
    print()
