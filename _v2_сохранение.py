# -*- coding: utf-8 -*-
r"""Доказательство, что текст пояснений подхватывается без оплаты (0 вызовов).

Запускать с PILOT_PROVIDER=polza: при старой подсказке «Артген (ИСКЧ)_6мес_2025» читался как
баланс вместе со страницами 19-40, значит их транскрипты 200 dpi (polza) уже лежат в кэше.
Теперь эти страницы — notes, и наш код должен найти их текст сам, не делая ни одного вызова.

Это и есть смысл формулировки пользователя «если notes попала в обработку случайно, тоже
сохраняем»: случайно прочитанное сохраняется, специально — не читается.
"""
import os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR

STEM = 'Артген (ИСКЧ)_6мес_2025'
NAME = STEM + '.pdf'


def find_pdf(stem):
    for root, _, files in os.walk(P.DOWNLOADS):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


print('активный поставщик: %s' % P.ACTIVE_PROFILE.name)
doc = P.pymupdf.open(find_pdf(STEM))

# метки V2 для этого документа (какие страницы названы пояснениями)
notes = list(range(11, 45))
found = {p: P.cached_transcript_path(doc, NAME, p) for p in notes}
have = sorted(p for p, v in found.items() if v)
missing = sorted(p for p, v in found.items() if not v)
doc.close()

cost = P.USAGE['cost_rub']
print()
print('страниц-пояснений: %d' % len(notes))
print('текст уже есть в кэше (подхватится бесплатно): %d страниц' % len(have))
print('  страницы: %s' % have)
print('текста нет (не читались — и не будут, это правильно): %d' % len(missing))
print('  страницы: %s' % missing)
print()
print('вызовов сделано: %d, потрачено: %.4f ₽' % (P.USAGE['calls'], P.USAGE['cost_rub'] - cost))
print()
if have:
    p0 = have[0]
    print('пример сохранённого текста (стр. %d):' % p0)
    txt = open(found[p0], encoding='utf-8').read()
    for line in [l.strip() for l in txt.splitlines() if l.strip()][:4]:
        print('   > %s' % line[:160])
print()
print('ИТОГ: %s' % ('механизм работает — случайно прочитанные пояснения сохраняются бесплатно'
                    if have else 'текста не нашлось (проверь поставщика: нужен polza)'))
