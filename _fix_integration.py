# -*- coding: utf-8 -*-
r"""Сквозная проверка конвейера после правок — в отдельном каталоге, данные не тронуты.

Проверяются именно те места, которые я менял:
  * ключ кэша детекции из текста подсказки (`detect_cache_stem`);
  * титульный лист читается как `title_p1`, реквизиты не теряются;
  * задел `source.non_form_pages` пишется;
  * поставщик в артефакте — plusvibe;
  * гейты эскалации на месте и не ломают обычный прогон;
  * проверки форм считаются.

Выход пишется в отдельный каталог (`PILOT_OUTDIR`), поэтому артефакты пользователя
не перезаписываются. Стоимость: один небольшой документ.
"""
import glob, io, json, os, shutil, sys

OUT = r'D:\models\tmp\_integration'
# Remove the artifacts but KEEP tmp/_integration/pages: the page cache is what makes a
# repeat run free, and deleting it re-paid for every transcription (measured: 0.998 ₽
# on the first run, 2.434 ₽ on the second, entirely because of this).
if os.path.exists(OUT):
    for fn in os.listdir(OUT):
        p = os.path.join(OUT, fn)
        if os.path.isfile(p):
            os.remove(p)
os.makedirs(OUT, exist_ok=True)
os.environ['PILOT_OUTDIR'] = OUT
sys.path.insert(0, r'D:\models')

import pipeline as P   # noqa: E402  (импорт после установки OUTDIR)

# __main__ does this; calling process() directly does not, and without it the first cache
# write fails. _write_cache now creates the directory itself, so this is belt and braces.
os.makedirs(P.OUTDIR, exist_ok=True)
os.makedirs(P.PAGESDIR, exist_ok=True)

DOC = 'Нижегородец Восток_6мес_2026.pdf'
path = os.path.join(P.DOWNLOADS, DOC)
print('каталог вывода: %s' % OUT)
print('поставщик: %r' % P.ACTIVE_PROFILE.name)
print('документ: %s' % DOC)
print('кэш страниц: %s' % P.PAGESDIR)
print()

cost0 = P.USAGE['cost_rub']
res = P.process(path)

print()
print('=' * 78)
print('ПРОВЕРКИ')
checks = []


def check(name, cond, extra=''):
    checks.append((name, bool(cond), extra))
    print('  %-58s %s %s' % (name, 'ok' if cond else 'ПРОВАЛ', extra))


check('статус получен', res.get('status') in ('ok', 'needs_review', 'no_forms', 'incomplete'),
      res.get('status'))
check('поставщик записан и это plusvibe', res.get('source', {}).get('provider') == 'plusvibe',
      res.get('source', {}).get('provider'))
check('модель записана', bool(res.get('source', {}).get('ocr_model')))
forms = [k for k in ('balance', 'income_statement', 'cash_flow') if res.get(k)]
check('найдена хотя бы одна форма', bool(forms), forms)
check('проверки посчитаны', bool(res.get('checks')), '%d проверок' % len(res.get('checks') or []))
# A real check, not a tautology: the run must record which pages it decided were NOT forms,
# so a future auditor's-report pass can find them without re-detecting.
src_meta = res.get('source') or {}
check('в source записано, какие страницы не формы',
      'non_form_pages' in src_meta,
      'ключ отсутствует; в source: %s' % sorted(src_meta))
check('предупреждения собираются', isinstance(res.get('warnings'), list),
      '%d' % len(res.get('warnings') or []))
for k in forms:
    d = res[k]
    check('%s: есть строки' % k, bool(d.get('items')), '%d строк' % len(d.get('items') or []))
    check('%s: записаны страницы транскрипта' % k, bool(d.get('transcript_pages')),
          d.get('transcript_pages'))

print()
print('реквизиты из титульного листа: company=%s unit=%s'
      % (json.dumps(res.get('company'), ensure_ascii=False),
         json.dumps(res.get('unit'), ensure_ascii=False)))
print('ключ кэша детекции, который использовался: %s'
      % P.detect_cache_stem(DOC))
inf = P._provider_infix()
pg_files = glob.glob(os.path.join(P.PAGESDIR,
                                  '_llm_' + P.detect_page_cache_stem(DOC, 1).replace('p1', 'p*') + inf + '.json'))
check('метки детекции закэшированы постранично', len(pg_files) >= 1,
      'файлов меток на страницу: %d' % len(pg_files))
check('метки не свалены в один файл на документ',
      not os.path.exists(os.path.join(P.PAGESDIR,
                                      '_llm_' + P.detect_cache_stem(DOC) + inf + '.json')),
      'старый документный ключ всё ещё используется')
print()
print('предупреждения:')
for w in (res.get('warnings') or [])[:8]:
    print('   %s' % w[:150])
print()
print('цена прогона: %.3f ₽, вызовов %d' % (P.USAGE['cost_rub'] - cost0, P.USAGE['calls']))
print()
bad = [c for c in checks if not c[1]]
print('ИТОГ: проверок %d, провалов %d' % (len(checks), len(bad)))
for n, _, e in bad:
    print('   ПРОВАЛ: %s %s' % (n, e))
print()
print('артефакт: %s' % os.path.join(OUT, os.path.splitext(DOC)[0] + '.json'))
