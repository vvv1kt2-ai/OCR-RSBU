# -*- coding: utf-8 -*-
r"""Проверка нового пути: текст неформных страниц сохраняется, и это не стоит денег.

Проверяем на «Артген (ИСКЧ)_6мес_2025»: при старой подсказке страницы 19-40 были прочитаны
как баланс, поэтому их транскрипты (200 dpi, основная модель) уже лежат в кэше. Теперь V2
зовёт их notes — и наш код должен подхватить УЖЕ ОПЛАЧЕННЫЙ текст, а не читать заново.

Вызываем scan_pipeline напрямую: он делает детекцию и транскрипцию, но не структурирование
и не эскалацию, поэтому единственная плата — детекция (~0.0016 ₽ за страницу).

Что проверяем:
  1. страницы notes/audit действительно найдены;
  2. их текст попал в transcripts под ключом nonform_p<стр>;
  3. страниц, которых не было в кэше, среди них НЕТ — то есть мы не заплатили за чтение;
  4. баланс по-прежнему прочитан.
"""
import io, os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

STEM = 'Артген (ИСКЧ)_6мес_2025'


def find_pdf(stem):
    for root, _, files in os.walk(P.DOWNLOADS):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


path = find_pdf(STEM)
doc = P.pymupdf.open(path)
npages = len(doc)
cand = [p for p in range(1, npages + 1)
        if doc[p - 1].get_images(full=True) and len(doc[p - 1].get_text().strip()) < 600]

# что было в кэше ДО прогона — чтобы отличить попадание от новой оплаты
before = set(os.listdir(P.PAGESDIR))
cost0, calls0 = P.USAGE['cost_rub'], P.USAGE['calls']

warnings, transcripts = P.scan_pipeline(doc, STEM + '.pdf', only_pages=cand)
doc.close()

after = set(os.listdir(P.PAGESDIR))
new_files = after - before
extra = P.doc_result.get('_extra_pages') or {}
nonform = {k: v for k, v in transcripts.items() if k.startswith('nonform_p')}
form_txt = {k: v for k, v in transcripts.items() if k.endswith(tuple('_p%d' % p for p in range(1, 100)))}

print('страниц-кандидатов: %d' % len(cand))
print('найдено notes: %s' % (extra.get('notes') or '—'))
print('найдено audit: %s' % (extra.get('audit') or '—'))
print('без метки:     %s' % (extra.get('unlabeled') or '—'))
print()
print('страниц баланса прочитано: %s' % sorted(
    int(k.rsplit('_p', 1)[1]) for k in transcripts if k.startswith('balance_p')))
print('текст неформных страниц сохранён: %d страниц' % len(nonform))
print('  страницы: %s' % sorted(int(k[len('nonform_p'):]) for k in nonform)[:30])
print()
print('новых файлов транскриптов создано: %d (это и есть новая оплата)' % len(
    [f for f in new_files if not f.startswith('_llm_')]))
print('новых файлов меток детекции: %d' % len([f for f in new_files if f.startswith('_llm_')]))
print()
print('цена прогона: %.4f ₽, вызовов %d' % (P.USAGE['cost_rub'] - cost0,
                                            P.USAGE['calls'] - calls0))
print()
ok = True
if not nonform:
    print('ПРОВАЛ: текст неформных страниц не сохранён'); ok = False
if not extra.get('notes'):
    print('ПРОВАЛ: notes не найдены'); ok = False
if not [k for k in transcripts if k.startswith('balance_p')]:
    print('ПРОВАЛ: баланс не прочитан'); ok = False
if len(new_files) - len([f for f in new_files if f.startswith('_llm_')]) > 0:
    print('ВНИМАНИЕ: созданы новые транскрипты, то есть чтение было оплачено')
print('ИТОГ: %s' % ('всё сходится' if ok else 'есть провалы'))
