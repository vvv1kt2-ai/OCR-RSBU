# -*- coding: utf-8 -*-
r"""Что на самом деле на страницах: признаки формы в готовых транскриптах (бесплатно).

Признаки:
  * заголовок формы — есть ли «Бухгалтерский баланс» / «Отчет о финансовых результатах»;
  * итоговый код — есть ли 1700 (баланс), 2410/2400 (ОФР), 4500 (ОДДС);
  * коды строк — сколько различных кодов 11xx/12xx/13xx/14xx/15xx/16xx/17xx видно.
"""
import io, glob, os, re, sys

PAGES = r'D:\models\extracted\pages'
STEM = sys.argv[1] if len(sys.argv) > 1 else 'НовосибирскАвтодор_6мес_2025'
DPI = sys.argv[2] if len(sys.argv) > 2 else '200'

files = sorted(glob.glob(os.path.join(PAGES, f'{STEM}_p*_{DPI}_*.md')),
               key=lambda f: int(re.search(r'_p(\d+)_', f).group(1)))
print('%s, dpi %s, транскриптов: %d' % (STEM, DPI, len(files)))
print()
print('%4s %9s %-28s %-26s %6s %6s %6s %6s %7s'
      % ('стр.', 'символов', 'заголовок формы', 'итоговый код', '1700', '2410', '4500', 'кодов', 'чисел'))
for f in files:
    p = int(re.search(r'_p(\d+)_', f).group(1))
    txt = io.open(f, encoding='utf-8').read()
    low = txt.lower()
    if 'бухгалтерский баланс' in low:
        head = 'Бухгалтерский баланс'
    elif 'финансовых результатах' in low:
        head = 'Отчет о фин. результатах'
    elif 'движении денежных средств' in low:
        head = 'Отчет о движении ден. ср.'
    elif 'пояснени' in low:
        head = 'Пояснения'
    elif 'аудиторск' in low:
        head = 'Аудиторское заключение'
    else:
        head = '—'
    codes = set(re.findall(r'\b(1[1-7]\d0|2[4-5]\d0|4[1-5]\d0)\b', txt))
    term = []
    for c, nm in (('1700', '1700'), ('2410', '2410'), ('2400', '2400'), ('4500', '4500')):
        if re.search(r'\b%s\b' % c, txt):
            term.append(nm)
    nums = len(re.findall(r'\d[\d\s]{2,}', txt))
    print('%4d %9d %-28s %-26s %6s %6s %6s %6d %7d'
          % (p, len(txt), head[:28], ','.join(term) or '—',
             'да' if '1700' in term else '—',
             'да' if '2410' in term else '—',
             'да' if '4500' in term else '—',
             len(codes), nums))
