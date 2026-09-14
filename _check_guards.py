# -*- coding: utf-8 -*-
"""Проверка: у каждого диагностического скрипта есть защита от импорта."""
import ast, io

GUARD = "if __name__ == '__main__':"
FILES = ['_pv_arbiter.py', '_pv_multi.py', '_pv_quality.py', '_pv_selfcheck.py',
         '_pv_verdict.py', '_provider_switch.py', 'verify_profiles.py']

bad = []
for f in FILES:
    t = io.open(f, encoding='utf-8').read()
    try:
        ast.parse(t)
        parses = True
    except SyntaxError as e:
        parses = False
        print('%-24s СИНТАКСИС: %s' % (f, e))
        bad.append(f)
        continue
    has = GUARD in t
    print('%-24s разбирается: %s  защита от импорта: %s'
          % (f, 'да' if parses else 'НЕТ', 'да' if has else 'НЕТ'))
    if not has:
        bad.append(f)

print()
print('без защиты: %s' % (', '.join(bad) if bad else 'нет'))
