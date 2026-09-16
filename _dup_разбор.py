# -*- coding: utf-8 -*-
r"""Что именно за дубли: две НАСТОЯЩИЕ строки (складывать) или дочерняя, повторившая код?

Это решающий вопрос перед правилом. Если дубль — это строка «в том числе» с тем же кодом, что у
родителя, то сложение УДВОИТ значение и испортит данные. Если это две самостоятельные строки
отчёта (как 1250 «Денежные средства» 4 070 и «Депозитные счета» 14 500) — складывать надо.

Печатаем окрестности каждого дубля по кодам, которые вообще влияют на свод:
1110, 1150, 1210, 1215, 1220, 1230, 1240, 1250, 1260, 1410, 1450, 1510, 1520, 1550.
"""
import io, os, re, glob, collections

PAGES = r'D:\models\extracted\pages'
INTEREST = {'1110', '1150', '1210', '1215', '1220', '1230', '1240', '1250', '1260',
            '1410', '1450', '1510', '1520', '1550'}
CELL_CODE = re.compile(r'\|\s*(\d{4})\s*\|')

best = {}
for f in glob.glob(os.path.join(PAGES, '*_p*_200_*.md')):
    b = os.path.basename(f)
    m = re.match(r'^(?P<doc>.+)_p(?P<page>\d+)_200_.*\.md$', b)
    if m:
        best.setdefault((m.group('doc'), int(m.group('page'))), f)

shown = 0
for (doc, page), f in sorted(best.items()):
    try:
        lines = io.open(f, encoding='utf-8', errors='replace').read().splitlines()
    except Exception:
        continue
    idx = collections.defaultdict(list)
    for i, ln in enumerate(lines):
        for c in CELL_CODE.findall(ln):
            if c in INTEREST:
                idx[c].append(i)
    dups = {c: v for c, v in idx.items() if len(v) >= 2}
    if not dups:
        continue
    print('=' * 100)
    print('%s  стр. %d   дубли: %s' % (doc, page, sorted(dups)))
    for c, v in sorted(dups.items()):
        lo = max(0, min(v) - 2)
        hi = min(len(lines), max(v) + 3)
        print('  --- код %s (строки %s)' % (c, [x + 1 for x in v]))
        for i in range(lo, hi):
            mark = ' <<<' if i in v else ''
            print('     %4d | %s%s' % (i + 1, lines[i].rstrip()[:120], mark))
    shown += 1
    if shown >= 8:
        print('\n...(показаны первые 8 страниц)')
        break
