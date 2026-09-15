# -*- coding: utf-8 -*-
r"""Выборочная проверка: что за страницы, у которых нет кодов строк.

Печатает первые строки выбранных страниц в файл, чтобы посмотреть их глазами и убедиться,
что признак «нет кодов строк» действительно указывает на пояснения, а не на что-то ещё.
"""
import io, json, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
PAGES = P.PAGESDIR
DST = r'D:\models\_notes_выборка.md'

CODE_RE = re.compile(r'\b(1[1-7]\d0|2[45]\d0|4[1-5]\d0)\b')
all_files = os.listdir(PAGES)

want = [
    ('Омега_6мес_2025', 'balance', 14),
    ('Моторные технологии_6мес_2026', 'balance', 21),
    ('Сибсульфур_6мес_2026', 'balance', 66),
    ('НовосибирскАвтодор_6мес_2026', 'cash_flow', 43),
    ('Артген (ИСКЧ)_6мес_2025', 'balance', 30),
    ('Артген (ИСКЧ)_6мес_2025', 'balance', 2),
    ('Артген (ИСКЧ)_6мес_2025', 'balance', 3),
]

lines = ['# Что за страницы без кодов строк (выборка)\n']
for stem, form, p in want:
    hits = [f for f in all_files if f.startswith(f'{stem}_p{p}_') and f.endswith('.md')]
    if not hits:
        lines.append(f'## {stem} стр. {p} — транскрипта нет\n')
        continue
    txt = io.open(os.path.join(PAGES, hits[0]), encoding='utf-8').read()
    codes = sorted(set(CODE_RE.findall(txt)))
    body = [l.strip() for l in txt.splitlines() if l.strip()][:6]
    lines.append(f'## {stem} — {form}, стр. {p}')
    lines.append(f'знаков {len(txt)}, кодов строк найдено: {len(codes)}'
                 + (f' ({", ".join(codes[:12])})' if codes else ' — НИ ОДНОГО'))
    lines.append('')
    for b in body:
        lines.append('> ' + b[:200])
    lines.append('')

io.open(DST, 'w', encoding='utf-8').write('\n'.join(lines))
print('записано: %s' % DST)
