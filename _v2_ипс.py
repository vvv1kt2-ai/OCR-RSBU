# -*- coding: utf-8 -*-
r"""Что случилось с ИПС_6мес_2026 в прогоне V2.

Артефакт пуст: ни баланса, ни ОФР, ни ОДДС, три проверки из трёх провалены. В бэкапе у того
же документа 23/14/12 строк. Значит либо детекция увела страницы не туда, либо вызовы
отбились поставщиком. Печатаем окно лога вокруг этого документа.
"""
import io

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
start = None
for i, l in enumerate(lines):
    if '== ИПС_6мес_2026.pdf' in l:
        start = i
        break
if start is None:
    print('документ в логе не найден')
else:
    for l in lines[start:start + 40]:
        s = l.strip()
        if not s:
            continue
        if 'HTTP 400' in s:
            s = s[:120] + ' ... [HTTP 400]'
        print(s[:190])
