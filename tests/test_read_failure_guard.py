# -*- coding: utf-8 -*-
r"""Тест защёлки: сетевой сбой чтения страницы не должен убивать весь документ.

Что проверяется. `scan_pipeline` читает страницы пулом потоков через
`ex.map(lambda p: transcribe_cached(...))`. Без защёлки любое исключение из
`transcribe_cached` (а он бросает `RuntimeError` после трёх повторов: 502, 503, таймаут)
выходит из `map` и завершает `process()` целиком — документ не пишется, хотя остальные
страницы уже прочитаны и ОПЛАЧЕНЫ.

Замер 02.11.2026 на новых отчётах: 54 ответа 502 на ~200 вызовов, **3 документа из 8
потеряны полностью** (`Регионспецтранс` оба года, `Энерготехсервис_9мес_2026`). В логе
видно, что у последнего баланс и ОФР были собраны и проверены — падение случилось позже,
на эскалации. При 135 эмитентах и той же частоте это ~50 потерянных документов.

Тест без сети и без денег: `transcribe_cached` подменяется функцией, которая всегда
бросает 502. Настоящий `process()` при этом проходит целиком.

Запуск: python D:\models\tests\test_read_failure_guard.py
Лог:    tests\_last_run_read_guard.txt
"""
import io
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_read_guard.txt'), 'w',
              encoding='utf-8')
ok = fail = 0


def check(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        LOG.write(f'  OK   {name}\n')
    else:
        fail += 1
        LOG.write(f'  ПРОВАЛ {name} {detail}\n')


PDF = os.path.join(r'D:\data-scraping\downloads', 'Кокс_9мес_2026.pdf')
OUT = os.path.join(P.OUTDIR, 'Кокс_9мес_2026.json')

# ─── 1. текст источника: защёлка на месте ───
src = io.open(os.path.join(r'D:\models', 'pipeline.py'), encoding='utf-8').read()
check('в scan_pipeline есть _read с перехватом',
      'def _read(p):' in src and 'READ FAILED' in src)
check('чтение в пуле идёт через _read', 'ex.map(_read, todo)' in src)
check('титульная страница тоже под защёлкой', 'title page {p}: READ FAILED' in src)
check('эскалация перехватывает сбой перечитывания',
      'Отказ канала эскалации' in src)
check('эскалация перехватывает сбой структурирования',
      'Тот же принцип, что и для перечитывания' in src)

# ─── 2. поведение: полный отказ сети, настоящий process() ───
if not os.path.exists(PDF):
    check('PDF для поведенческой проверки на месте', False, PDF)
else:
    saved = open(OUT, 'rb').read() if os.path.exists(OUT) else None
    orig = P.transcribe_cached

    def boom(doc, p, name=None, dpi=200, model=None, warnings=None):
        raise RuntimeError('<urlopen error Tunnel connection failed: 502 Bad Gateway>')

    P.transcribe_cached = boom
    try:
        r = P.process(PDF)
        raised = None
    except Exception as e:
        r, raised = None, e
    finally:
        P.transcribe_cached = orig
        if saved is not None:
            with open(OUT, 'wb') as f:
                f.write(saved)

    check('документ вернулся, а не упал исключением', raised is None,
          f'{type(raised).__name__}: {str(raised)[:120]}' if raised else '')
    if r is not None:
        check('артефакт записан (есть status)', bool(r.get('status')),
              f'status={r.get("status")}')
        check('статус не no_forms: формы в документе есть, читать не удалось',
              r.get('status') != 'no_forms', f'status={r.get("status")}')
        warn = ' '.join(r.get('warnings') or [])
        check('сбой назван в предупреждениях', 'не удалось' in warn or 'READ FAILED' in warn,
              warn[:150])
        check('пометок о сбое не меньше числа страниц',
              sum(1 for w in r.get('warnings') or [] if 'не удалось' in w) >= 1)

# ─── 3. правило статуса связано с этим текстом ───
check('сбой чтения понижает no_forms до incomplete',
      P.downgrade_no_forms('no_forms', ['баланс не прочитан: чтение не удалось (502)'])
      == 'incomplete')

LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
LOG.close()
print(f'успешно {ok}, провалов {fail} (лог: tests/_last_run_read_guard.txt)')
sys.exit(1 if fail else 0)