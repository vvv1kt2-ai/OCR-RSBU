# -*- coding: utf-8 -*-
r"""Почему у двух документов стало меньше данных.

Случай 1 — Рекорд трейд_6мес_2026 / ОДДС: было 42 строки (4111...4329), стало 13.
  Гипотеза: раньше работала текстовая ветка (её разбор по правилам даёт детальные строки),
  теперь документ ушёл в скановую и структурирование LLM детальные строки потеряло.
  Проверяем по логу: какая ветка отработала.

Случай 2 — Моторные технологии_6мес_2025 / баланс: 5 строк потеряли ПЕРВУЮ колонку
  (1200, 1220, 1230, 1250, 1260). Остальные колонки на месте. Гипотеза: раньше первая
  колонка добиралась из пояснений, которые вклеивались в транскрипт баланса (22 страницы!),
  а теперь пояснения не читаются. Проверяем по транскрипту страниц баланса: есть ли там
  первая колонка. Это бесплатно — транскрипты уже оплачены.
"""
import io, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

RAW = r'D:\models\_v2_прогон_raw.log'


def read_log(path):
    b = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-16', 'cp1251'):
        try:
            t = b.decode(enc)
            if t.count('\x00') < len(t) // 10:
                return t
        except Exception:
            pass
    return b.decode('utf-8', 'replace')


lines = [l.rstrip() for l in read_log(RAW).splitlines()]
print('=== 1. Рекорд трейд_6мес_2026 — какая ветка отработала')
for i, l in enumerate(lines):
    if l.strip().startswith('== Рекорд трейд_6мес_2026.pdf'):
        for x in lines[i:i + 14]:
            s = x.strip()
            if s:
                print('   ' + (s[:150] + ' ...' if 'HTTP' in s else s[:150]))
        break

print()
print('=== 2. Моторные технологии_6мес_2025 — что в транскриптах страниц баланса')
stem = 'Моторные технологии_6мес_2025'
import glob
for p in (2, 3, 4):
    hits = [f for f in os.listdir(P.PAGESDIR)
            if f.startswith('%s_p%d_' % (stem, p)) and f.endswith('.md')]
    if not hits:
        print('   стр. %d: транскрипта нет' % p)
        continue
    # предпочитаем plusvibe
    hits.sort(key=lambda f: ('_pv_' not in f, f))
    txt = io.open(os.path.join(P.PAGESDIR, hits[0]), encoding='utf-8').read()
    head = [l.strip() for l in txt.splitlines() if l.strip()][:4]
    print('   --- стр. %d (%s, %d знаков)' % (p, hits[0][-24:], len(txt)))
    for h in head:
        print('       > %s' % h[:170])
    # ищем строки 1200/1220/1230/1250/1260 и печатаем их целиком
    for code in ('1200', '1220', '1230', '1250', '1260'):
        m = [l for l in txt.splitlines() if re.search(r'\|\s*%s\s*\|' % code, l)]
        if m:
            print('       %s: %s' % (code, m[0].strip()[:170]))
    print()
