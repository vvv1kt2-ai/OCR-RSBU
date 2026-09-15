# -*- coding: utf-8 -*-
r"""Прогон всего пилота (41 документ) на plusvibe с подсказкой V2.

Зачем: измерить ДЕНЬГИ, а не страницы. Страницы измерены отдельно (406 -> 183, -55%), но
эскалация — 51% цены пилота, а она зависит от арифметики формы, которую пояснения и ломали.
Проекция по страницам предполагает неизменное число эскалаций; этот прогон покажет, так ли это.

Что важно перед запуском:
  * артефакты extracted/*.json будут ПЕРЕЗАПИСАНЫ — бэкап сделан в extracted/_backup_v2_before;
  * кэш polza не переиспользуется (суффикс _pv), поэтому чтение оплачивается заново;
  * reasoning не трогаем: сравнение с базой 116.23 ₽ должно быть честным.

Прогресс пишется построчно в _v2_прогон.log после каждого документа, поэтому падение
процесса не уничтожит уже оплаченный результат.
"""
import io, json, os, sys, time

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
LOG = r'D:\models\_v2_прогон.log'


def find_pdf(stem):
    for root, _, files in os.walk(P.DOWNLOADS):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


def log(line):
    with io.open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line, flush=True)


os.makedirs(P.OUTDIR, exist_ok=True)
os.makedirs(P.PAGESDIR, exist_ok=True)
io.open(LOG, 'w', encoding='utf-8').write(
    'прогон V2 на %s, начат %s\n' % (P.ACTIVE_PROFILE.name, time.strftime('%Y-%m-%d %H:%M:%S')))

arts = sorted(f for f in os.listdir(OUT) if f.endswith('.json') and not f.startswith('_'))
log('документов к прогону: %d' % len(arts))

t0 = time.time()
rows = []
for i, fn in enumerate(arts, 1):
    stem = os.path.splitext(fn)[0]
    path = find_pdf(stem)
    if not path:
        log('%3d/%d  %-40s PDF НЕ НАЙДЕН' % (i, len(arts), stem[:40]))
        continue
    c0, k0 = P.USAGE['cost_rub'], P.USAGE['calls']
    r = None
    try:
        r = P.process(path)
        status, err = r.get('status'), ''
    except Exception as e:
        status, err = 'failed', str(e)[:120]
        log('%3d/%d  %-40s ИСКЛЮЧЕНИЕ: %s' % (i, len(arts), stem[:40], err))
    dc = P.USAGE['cost_rub'] - c0
    dk = P.USAGE['calls'] - k0
    pages = set()
    if isinstance(r, dict):
        for k in ('balance', 'income_statement', 'cash_flow'):
            d = r.get(k)
            if d:
                pages |= set(d.get('transcript_pages') or [])
    esc = sum(1 for w in (r.get('warnings') or []) if 'эскалац' in w) if isinstance(r, dict) else 0
    rows.append((stem, status, dc, dk, len(pages), esc))
    log('%3d/%d  %-40s %-11s %6.3f ₽ %4d вызовов %3d стр. эскалаций:%d'
        % (i, len(arts), stem[:40], status, dc, dk, len(pages), esc))

log('')
log('ИТОГО: %.2f ₽, вызовов %d, документов %d, время %.1f мин'
    % (P.USAGE['cost_rub'], P.USAGE['calls'], len(rows), (time.time() - t0) / 60))
log('провалов: %d' % sum(1 for r in rows if r[1] in ('failed', None)))
log('документов с эскалацией: %d, всего предупреждений об эскалации: %d'
    % (sum(1 for r in rows if r[5]), sum(r[5] for r in rows)))
log('страниц прочитано: %d' % sum(r[4] for r in rows))
json.dump({'provider': P.ACTIVE_PROFILE.name, 'usage': P.USAGE,
           'rows': [dict(zip(('stem', 'status', 'cost', 'calls', 'pages', 'esc'), r))
                    for r in rows]},
          io.open(r'D:\models\_v2_прогон.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
log('сводка: _v2_прогон.json')
