# -*- coding: utf-8 -*-
r"""Сколько страниц конвейер будет читать при новой подсказке — по всему пилоту.

Это главный числовой ответ на вопрос «сколько стоит возврат категорий notes/audit».
Считать «сколько страниц формы» по одному прогону нельзя (детекция не воспроизводится),
но здесь задача другая: не сравнить две подсказки, а получить ОБЪЁМ РАБОТЫ при той, которую
выбрал пользователь. Объём — это то, что оплачивается, и он измеряется напрямую.

Как считается:
  кандидаты   — страницы-картинки (ровно то, что конвейер отдаёт в детекцию);
  формы V2    — что V2 назвала balance/income_statement/cash_flow;
  к чтению    — формы V2, отфильтрованные wanted_forms (у документов 2025 г. читается
                только баланс) плюс титульная страница, которую конвейер читает всегда;
  было        — страницы, записанные в артефактах (что читалось при V1).

Метки кэшируются постранично обычным ключом, поэтому повторный запуск бесплатен.
"""
import io, json, os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'


def find_pdf(stem):
    for root, _, files in os.walk(P.DOWNLOADS):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


arts = sorted(f for f in os.listdir(OUT) if f.endswith('.json') and not f.startswith('_'))
cost0, calls0 = P.USAGE['cost_rub'], P.USAGE['calls']
rows = []
for i, fn in enumerate(arts, 1):
    stem = os.path.splitext(fn)[0]
    path = find_pdf(stem)
    if not path:
        print('%s: PDF не найден' % stem); continue
    try:
        r = json.load(io.open(os.path.join(OUT, fn), encoding='utf-8'))
    except Exception:
        r = {}
    before = set()
    for key in ('balance', 'income_statement', 'cash_flow'):
        d = r.get(key)
        if d:
            before |= set(d.get('transcript_pages') or [])

    doc = P.pymupdf.open(path)
    npages = len(doc)
    cand = [p for p in range(1, npages + 1)
            if doc[p - 1].get_images(full=True) and len(doc[p - 1].get_text().strip()) < 600]
    if not cand:
        doc.close()
        rows.append((stem, npages, 0, 0, 0, 0, 0, 0, len(before)))
        continue
    try:
        pm = P.detect_pages_per_page(doc, cand, npages, [], stem + '.pdf')
    except Exception as e:
        print('%s: детекция упала: %s' % (stem, e)); doc.close(); continue
    doc.close()

    forms = {}
    for x in pm:
        if x.get('form') in P.FORM_LABELS:
            forms.setdefault(x['form'], []).append(x['page'])
    notes = sum(1 for x in pm if x.get('form') == 'notes')
    audit = sum(1 for x in pm if x.get('form') == 'audit')
    unlab = sum(1 for x in pm if x.get('form') not in P.PAGE_LABELS)

    want = P.wanted_forms(stem + '.pdf')
    to_read = {1} | {p for k, v in forms.items() if (not want or k in want) for p in v}
    n_forms = sum(len(v) for v in forms.values())
    rows.append((stem, npages, len(cand), n_forms, len(to_read), notes, audit, unlab,
                 len(before)))
    if i % 5 == 0 or i == len(arts):
        print('  ... %d из %d, потрачено %.4f ₽' % (i, len(arts), P.USAGE['cost_rub'] - cost0))

print()
print('%-34s %5s %5s %6s %7s %6s %5s %6s %6s'
      % ('документ', 'стр.', 'канд.', 'формV2', 'к чтению', 'notes', 'audit', 'безМ', 'было'))
print('-' * 96)
for stem, npages, nc, nf, tr, notes, audit, unlab, before in rows:
    flag = ''
    if unlab:
        flag += ' *'
    print('%-34s %5d %5d %6d %7d %6d %5d %6d %6d%s'
          % (stem[:34], npages, nc, nf, tr, notes, audit, unlab, before, flag))
print('-' * 96)
S = lambda i: sum(r[i] for r in rows)
print('%-34s %5d %5d %6d %7d %6d %5d %6d %6d'
      % ('ИТОГО', S(1), S(2), S(3), S(4), S(5), S(6), S(7), S(8)))
print()
print('к чтению было: %d страниц, станет: %d страниц' % (S(8), S(4)))
if S(8):
    print('изменение: %+d страниц (%+.0f%%)' % (S(4) - S(8), 100.0 * (S(4) - S(8)) / S(8)))
print()
print('цена замера: %.4f ₽, вызовов %d' % (P.USAGE['cost_rub'] - cost0, P.USAGE['calls'] - calls0))
print('("*" в последней колонке = есть страницы, которым детекция не дала метку вовсе)')
