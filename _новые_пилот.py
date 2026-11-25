# -*- coding: utf-8 -*-
r"""Пилот на НОВЫХ отчётах (9мес): прогон конвейера + поиск провалов баланса.

Зачем отдельный скрипт вместо run_batch.py: у run_batch.py список жёстко зашит на
`_6мес_`, а нам нужны новые отчёты. Логика та же — `pipeline.process()` без обёрток,
поэтому пишется то же, что пишет производство, и кэш остаётся годным для будущего прогона.

Печатает по каждому документу: страниц, статус, стоимость, провалы правил баланса.
Провал баланса — единственное, что запускает эскалацию (pipeline.py, ветка скана),
поэтому именно эти документы попадают в A/B.

Запуск:  python _новые_пилот.py            (дефолтный список)
         python _новые_пилот.py файл1.pdf файл2.pdf
"""
import json, os, sys, time

sys.path.insert(0, r'D:\models')
import pipeline as P

SRC = r'D:\data-scraping\downloads'

# Самые короткие сканы без текстового слоя — их прогон дешевле всего, а вопрос
# («сходится ли баланс на новых отчётах») от длины документа не зависит.
DEFAULT = [
    'Кокс_9мес_2025.pdf',
    'Автобан_9мес_2026.pdf',
    'Регионспецтранс_9мес_2026.pdf',
    'Энерготехсервис_9мес_2026.pdf',
    'Энерготехсервис_9мес_2025.pdf',
    'Регионспецтранс_9мес_2025.pdf',
    'Рубеж_9мес_2026.pdf',
    'Рубеж_9мес_2025.pdf',
]


def run(names):
    rows = []
    for i, n in enumerate(names, 1):
        path = n if os.path.isabs(n) else os.path.join(SRC, n)
        print(f'--- [{i}/{len(names)}] {os.path.basename(path)}', flush=True)
        t0 = time.time()
        P.USAGE['calls'] = 0
        P.USAGE['prompt'] = 0
        P.USAGE['completion'] = 0
        P.USAGE['cost_rub'] = 0.0
        try:
            r = P.process(path)
        except Exception as e:
            import traceback
            traceback.print_exc()
            rows.append(dict(file=os.path.basename(path), error=str(e)[:200]))
            continue
        bal = r.get('balance') or {}
        items = bal.get('items') or []
        chks = [c for c in r.get('checks', []) if c.get('form') == 'balance']
        fails = [c for c in chks if not c.get('ok') and c.get('verdict') != 'n/a']
        row = dict(
            file=os.path.basename(path),
            pages=(r.get('source') or {}).get('pages_total'),
            status=r.get('status'),
            cost=round(P.USAGE['cost_rub'], 3),
            calls=P.USAGE['calls'],
            rows=sum(1 for it in items if it.get('code')),
            checks=len(chks),
            fails=len(fails),
            fail_rules=[c.get('rule') for c in fails][:5],
            esc_pages=(bal.get('transcript_pages') or [])[:10],
            minutes=round((time.time() - t0) / 60.0, 1),
        )
        rows.append(row)
        print(f'    -> status={row["status"]} cost={row["cost"]} ₽ '
              f'checks={row["checks"]} fails={row["fails"]} {row["minutes"]} мин', flush=True)
    out = r'D:\models\_новые_пилот.json'
    json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print()
    print('=== ИТОГ ===')
    tot = sum(r.get('cost') or 0 for r in rows)
    for r in rows:
        print(f'  {r.get("file", "?"):40} status={str(r.get("status")):12} '
              f'провалов={r.get("fails", "-")} {r.get("cost", 0)} ₽')
    print(f'  всего {tot:.2f} ₽; документов с провалом баланса: '
          f'{sum(1 for r in rows if (r.get("fails") or 0) > 0)} из {len(rows)}')
    print(f'  -> {out}')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:]]
    run(args or DEFAULT)