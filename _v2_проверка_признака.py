# -*- coding: utf-8 -*-
r"""Проверка признака: не врёт ли он? Сверяем предсказание с тем, что реально было в прогоне.

Скрипт _v2_пустые.py назвал 9 документов, которые «идут текстовой веткой, форм в слое нет,
но сканы есть» — то есть должны выйти пустыми. Но три из них (НовосибирскАвтодор_6мес_2025,
Эфферон_6мес_2025, ИПС_6мес_2026) участвовали в прогоне, и двое выдали данные. Значит признак
может быть слишком грубым. Смотрим по логу: какую ветку выбрал конвейер и что нашёл.
"""
import io, re

RAW = r'D:\models\_v2_прогон_raw.log'
SUSPECT = ['НовосибирскАвтодор_6мес_2025', 'Эфферон_6мес_2025', 'ИПС_6мес_2026']


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
for stem in SUSPECT:
    start = None
    for i, l in enumerate(lines):
        if l.strip().startswith('== %s.pdf' % stem):
            start = i
            break
    print('=' * 90)
    if start is None:
        print('%s — в прогоне не участвовал' % stem)
        continue
    print('%s' % stem)
    for l in lines[start:start + 12]:
        s = l.strip()
        if not s:
            continue
        if 'HTTP 400' in s:
            s = s[:100] + ' ... [HTTP 400]'
        print('   ' + s[:170])
    print()
