# -*- coding: utf-8 -*-
r"""Проверка: узнаёт ли новая подсказка страницы пояснений, которые мы уже опознали вручную.

Это не замер «сколько страниц», а точечная проверка на известных страницах. Число страниц
формы мерить нельзя: детекция не воспроизводится (согласие 57-96% между прогонами одной и
той же подсказки), поэтому разница в количестве ничего не доказывает. А вот ответ про
КОНКРЕТНУЮ страницу, про которую мы точно знаем, что это пояснения, — доказывает.

Известные страницы пояснений (проверены глазами по транскриптам, см. `_notes_выборка.md`):
  Артген (ИСКЧ)_6мес_2025   стр. 30 — «4.1. Наличие и движение основных средств»
  Омега_6мес_2025           стр. 14 — «1.5. Незаконченные и неоформленные НИОКР»
  НовосибирскАвтодор_6мес_2026 стр. 43 — «4. Основные средства (ОС)», была помечена cash_flow

Ждём от новой подсказки метку `notes` на этих страницах. Для контроля берём настоящую
страницу баланса «Артген (ИСКЧ)_6мес_2025» стр. 2 (шапка «Форма 0710001 с. 2», 19 кодов
строк) — она обязана остаться `balance`.
"""
import io, os, sys, collections

sys.path.insert(0, r'D:\models')
import pipeline as P

CASES = [
    ('Артген (ИСКЧ)_6мес_2025', {2: 'balance', 30: 'notes'}),
    ('Омега_6мес_2025', {14: 'notes'}),
    ('НовосибирскАвтодор_6мес_2026', {43: 'notes'}),
]
REPS = 3


def find_pdf(stem):
    for root, _, files in os.walk(P.DOWNLOADS):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


cost0, calls0 = P.USAGE['cost_rub'], P.USAGE['calls']
total, ok = 0, 0
for stem, expect in CASES:
    path = find_pdf(stem)
    if not path:
        print('%s: PDF не найден' % stem); continue
    doc = P.pymupdf.open(path)
    npages = len(doc)
    cand = [p for p in range(1, npages + 1)
            if doc[p - 1].get_images(full=True) and len(doc[p - 1].get_text().strip()) < 600]
    print('=' * 74)
    print('%s — страниц %d, кандидатов %d' % (stem, npages, len(cand)))
    want = [p for p in expect if p in cand]
    if not want:
        print('   проверяемые страницы %s не входят в кандидатов — проверка неприменима'
              % sorted(expect))
        doc.close()
        continue
    got = collections.defaultdict(collections.Counter)
    for rep in range(1, REPS + 1):
        for p in want:
            def call(p=p):
                try:
                    return P.detect_one_page(doc, p, npages)
                except Exception as e:
                    return f'ошибка: {e}'
            lab = P.cached_llm(
                f'{stem}_v2check_r{rep}_p{p}_g3', call)
            got[p][lab] += 1
    for p in want:
        exp = expect[p]
        c = got[p]
        best, n = c.most_common(1)[0]
        total += 1
        good = best == exp
        ok += 1 if good else 0
        print('   стр. %-4d ждём %-8s получили %-8s (%d из %d прогонов) %s'
              % (p, exp, best, n, REPS, 'ВЕРНО' if good else 'НЕ СОВПАЛО'))
        if len(c) > 1:
            print('        разброс: %s' % dict(c))
    doc.close()

print()
print('=' * 74)
print('итог: верных ответов %d из %d' % (ok, total))
print('цена проверки: %.4f ₽, вызовов %d' % (P.USAGE['cost_rub'] - cost0,
                                              P.USAGE['calls'] - calls0))
print()
print('Читать так: «ВЕРНО» на странице пояснений = подсказка отделяет пояснения от формы,')
print('и они больше не будут читаться как баланс.')
