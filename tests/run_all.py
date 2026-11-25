# -*- coding: utf-8 -*-
r"""Прогон всех тестов каталога tests/ и сводка по ним.

Зачем отдельный файл. Тесты писались в разное время и печатают итог ЧЕТЫРЬМЯ разными
формулировками: «успешно N, провалов M», «N OK, M провал(ов)», «passed: N failed: M»,
«пройдено N, провалено M». Прогнать их одной командой и увидеть общий счёт было нельзя —
приходилось запускать по одному и читать глазами. Здесь итог разбирается по всем
известным формулировкам, и если формулировка незнакомая, файл попадает в отдельный
список «не разобран», а не молча считается пройденным: молчаливый ноль опаснее провала.

Каждый тест запускается отдельным процессом и в рабочем каталоге D:\models — тесты
кладут рядом свои логи (tests\_last_run_*.txt) и пишут во временные каталоги.

Запуск: python D:\models\tests\run_all.py
"""
import os
import re
import subprocess
import sys

PY = sys.executable
TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)

# Известные формулировки итога. Порядок не важен: берётся первая совпавшая.
PATTERNS = [
    r'успешно\s+(\d+),\s+провалов\s+(\d+)',
    r'(\d+)\s+OK,\s+(\d+)\s+провал',
    r'passed:\s*(\d+)\s+failed:\s*(\d+)',
    r'ИТОГ:\s*(\d+)\s+успешно,\s*(\d+)\s+провалено',
    r'пройдено\s+(\d+),\s+провалено\s+(\d+)',
]


def parse(out):
    """(ok, fail) или (None, None), если итог не опознан."""
    for p in PATTERNS:
        m = re.search(p, out)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def main():
    files = sorted(f for f in os.listdir(TESTS)
                   if f.startswith('test_') and f.endswith('.py'))
    tot_ok = tot_fail = 0
    failed, unparsed = [], []
    for f in files:
        r = subprocess.run([PY, os.path.join(TESTS, f)],
                           capture_output=True, text=True, cwd=ROOT)
        out = (r.stdout or '') + (r.stderr or '')
        ok, fl = parse(out)
        if ok is None:
            unparsed.append(f)
            print(f'?    {f:38s} итог не опознан (код возврата {r.returncode})')
            if r.returncode:
                failed.append(f)
            continue
        tot_ok += ok
        tot_fail += fl
        if fl:
            failed.append(f)
        print(f'{"ok  " if not fl else "ПРОВАЛ"} {f:38s} {ok:3d} ok, {fl} провалов')
    print('-' * 62)
    print(f'ФАЙЛОВ: {len(files)}   ИТОГО: успешно {tot_ok}, провалов {tot_fail}')
    if unparsed:
        print('НЕ РАЗОБРАН ВЫВОД:', ', '.join(unparsed))
    if failed:
        print('ФАЙЛЫ С ПРОВАЛАМИ:', ', '.join(failed))
    return 1 if (tot_fail or failed) else 0


if __name__ == '__main__':
    sys.exit(main())
