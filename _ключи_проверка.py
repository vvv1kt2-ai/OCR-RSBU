# -*- coding: utf-8 -*-
r"""Какие ключи лежат в файле учётных данных — по именам и численно, без значений.

Сами значения не печатаются: нужен только факт наличия, длина и контрольная сумма,
чтобы можно было понять, тот ли это ключ, не показывая секрет.
"""
import hashlib, io, re

P = r'C:\Users\1\.dsh\.credentials.yaml'
raw = io.open(P, encoding='utf-8').read()
print('файл: %s' % P)
print('размер %d байт, непустых строк %d' % (len(raw), len(raw.splitlines())))
print()
print('%-28s %6s %12s' % ('имя', 'длина', 'sha1'))
print('-' * 50)
found = []
for line in raw.splitlines():
    line = line.rstrip()
    if not line.strip() or line.strip().startswith('#'):
        continue
    m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$', line)
    if not m:
        continue
    name = m.group(1)
    val = m.group(2).strip().strip('"').strip("'")
    if not val or val in ('null', '~'):
        continue
    found.append(name)
    print('%-28s %6d %12s' % (name, len(val), hashlib.sha1(val.encode()).hexdigest()[:12]))
print()
print('всего ключей: %d' % len(found))
print()
if 'DEEPSEEK_API_KEY' in found:
    print('DEEPSEEK_API_KEY присутствует — значит поиск падает не из-за отсутствия ключа,')
    print('а из-за состояния счёта на стороне DeepSeek.')
else:
    print('DEEPSEEK_API_KEY отсутствует в этом файле.')
