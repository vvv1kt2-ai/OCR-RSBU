# -*- coding: utf-8 -*-
r"""Контекст отказов HTTP 400: какой вызов и с какими параметрами не принял поставщик.

Два документа из 41 упали целиком (5% пилота). Отказ пришёл от поставщика с сообщением
«Некорректный запрос: проверьте параметры и формат запроса». Чтобы понять, наш это дефект
(слишком большой запрос, лишний параметр) или сбой площадки, смотрим строки вокруг отказа:
имя документа, последние успешные вызовы и их размеры.
"""
import io, re

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


lines = read_log(RAW).splitlines()
idx = [i for i, l in enumerate(lines) if 'HTTP 400' in l and 'attempt 1' in l]
print('первых отказов (attempt 1): %d' % len(idx))
for i in idx[:3]:
    print()
    print('=' * 90)
    for j in range(max(0, i - 9), min(len(lines), i + 2)):
        s = lines[j].strip()
        if s:
            print(('>>> ' if j == i else '    ') + s[:200])
