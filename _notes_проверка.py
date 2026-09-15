# -*- coding: utf-8 -*-
r"""Есть ли в формах страницы, которые на самом деле не формы.

Две предыдущие версии этой проверки были неверны, и обе — из-за признака, а не из-за данных:

1. По слову «пояснения» — а это КОЛОНКА официальной формы баланса (0710001), она стоит
   почти на каждой странице настоящего баланса. Объявила пояснениями 133 страницы из 384.
2. По словам «ФСБУ», «расшифровка», «учётная политика» — а в самой форме есть строки вроде
   «Резервы, образованные в соответствии с законодательством», и признак снова ловил
   настоящий баланс. 52 страницы, из них проверенные вручную (ИПС стр. 4, Байсэл стр. 4)
   оказались обычными продолжениями баланса с шапкой «Форма 0710001 с.2».

Надёжный признак — шапка формы. Продолжение формы несёт «Форма 07100XX с. N»; текстовая
страница пояснений её не несёт. Поэтому страница считается настоящей формой, если у неё
есть шапка формы ИЛИ итоговый код (1700 / 2410 / 2400 / 4500). Всё остальное — подозрение.
"""
import io, json, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
PAGES = P.PAGESDIR

FORM_HEAD = re.compile(r'Форма\s*0710\d{3}', re.I)
TERMINAL = {'balance': ('1700',), 'income_statement': ('2410', '2400'), 'cash_flow': ('4500',)}

arts = [f for f in os.listdir(OUT) if f.endswith('.json') and not f.startswith('_')]
print('проверяю артефактов: %d' % len(arts))
print()

all_files = os.listdir(PAGES)
suspect, checked, missing, genuine = [], 0, 0, 0
for fn in sorted(arts):
    try:
        r = json.load(io.open(os.path.join(OUT, fn), encoding='utf-8'))
    except Exception:
        continue
    stem = os.path.splitext(fn)[0]
    for key in ('balance', 'income_statement', 'cash_flow'):
        d = r.get(key)
        if not d:
            continue
        for p in (d.get('transcript_pages') or []):
            hits = [f for f in all_files if f.startswith(f'{stem}_p{p}_') and f.endswith('.md')]
            if not hits:
                missing += 1
                continue
            txt = io.open(os.path.join(PAGES, hits[0]), encoding='utf-8').read()
            checked += 1
            has_head = bool(FORM_HEAD.search(txt))
            has_term = any(re.search(r'\b%s\b' % t, txt) for t in TERMINAL[key])
            if has_head or has_term:
                genuine += 1
            else:
                suspect.append((stem, key, p, len(txt)))

print('страниц формы проверено: %d' % checked)
print('   из них признаны настоящими (шапка формы или итоговый код): %d' % genuine)
print('   транскрипт не найден: %d' % missing)
print()
if not suspect:
    print('Страниц без признаков формы НЕТ — все прочитанные страницы форм действительно формы.')
else:
    print('БЕЗ ПРИЗНАКОВ ФОРМЫ: %d страниц' % len(suspect))
    print()
    print('%-40s %-17s %5s %8s' % ('документ', 'форма', 'стр.', 'знаков'))
    for stem, key, p, n in suspect[:35]:
        print('%-40s %-17s %5d %8d' % (stem[:40], key, p, n))
    if len(suspect) > 35:
        print('... и ещё %d' % (len(suspect) - 35))
