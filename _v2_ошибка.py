# -*- coding: utf-8 -*-
r"""Расшифровка ошибки HTTP 400, из-за которой упали два документа.

Сообщение приходит как repr байтовой строки в escape-последовательностях:
b'{"error":{"message":"\xd0\x9d\xd0\xb5..."}}' — то есть русский текст в UTF-8, показанный
через \xNN. Читаем, декодируем и печатаем по-русски, чтобы понять, наш это дефект запроса
или отказ поставщика.
"""
import io, json, re

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


t = read_log(RAW)
seen = {}
for line in t.splitlines():
    if 'HTTP 400' not in line:
        continue
    m = re.search(r"b'(\{.*?\})'", line)
    if not m:
        continue
    raw = m.group(1)
    try:
        # repr-level: turn \xNN and \uNNNN into real characters
        decoded = raw.encode('latin-1', 'backslashreplace').decode('unicode_escape')
        obj = json.loads(decoded)
        msg = obj.get('error', {}).get('message', '')
    except Exception as e:
        msg = '(не разобрать: %s) %s' % (e, raw[:120])
    seen[msg] = seen.get(msg, 0) + 1

print('уникальных сообщений: %d' % len(seen))
for msg, n in sorted(seen.items(), key=lambda kv: -kv[1]):
    print()
    print('встретилось %d раз:' % n)
    print('  %s' % msg[:600])
