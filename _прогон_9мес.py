# -*- coding: utf-8 -*-
r"""Ночной прогон новых отчётов 9мес — с надзором, повторами и отчётом к утру.

Зачем надзор. Прогон идёт без человека 5 часов. Три вещи ломают такой прогон, и все три
здесь закрыты:
  1. воркер завис на одном документе (сеть «висит» без ошибки) — по таймауту процесс
     снимается, документ возвращается в очередь;
  2. документ упал, не оставив артефакта — он повторяется один раз, и только потом
     попадает в список неудач;
  3. прогонщик завершился, а работа осталась — повторный запуск продолжит с того же места:
     готовые артефакты пропускаются, оплаченное лежит в кэше страниц.

Каждый документ — отдельный процесс. Это не оптимизация: в `pipeline.py` есть глобальный
`doc_result`, который заполняет `scan_pipeline`, и два документа в одном процессе перетёрли
бы формы друг друга.

По завершении пишется `_ПРОГОН_ОТЧЁТ.md`: статусы, неудачи, стоимость по логам вызовов.

Запуск:  python _прогон_9мес.py [--workers 3] [--timeout 45]
"""
import json, os, re, subprocess, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DL = r'D:\data-scraping\downloads'
OUT = os.path.join(HERE, 'extracted')
LOG = os.path.join(HERE, 'tmp')
SUMMARY = os.path.join(HERE, '_прогон_9мес.json')
REPORT = os.path.join(HERE, '_ПРОГОН_ОТЧЁТ.md')
PY = sys.executable

MAX_ATTEMPTS = 2


def todo_list():
    names = sorted(f for f in os.listdir(DL) if re.search(r'_9мес_\d{4}\.pdf$', f))
    return [n for n in names if not os.path.exists(os.path.join(OUT, n[:-4] + '.json'))]


def log_cost(path):
    """Стоимость документа по строкам `[llm] ... cost=X.XXRUB` в его логе."""
    if not os.path.exists(path):
        return None
    total = 0.0
    seen = False
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.search(r'cost=([\d.]+)RUB', line)
        if m:
            total += float(m.group(1)); seen = True
    return round(total, 3) if seen else None


def write_report(done, failed, elapsed):
    """Отчёт к утру: что прочитано, что нет и сколько это стоило."""
    lines = ['# Прогон новых отчётов 9мес', '']
    lines.append(f'Завершён: {time.strftime("%d.%m.%Y %H:%M")}. '
                 f'Время прогона: {elapsed / 3600:.1f} ч.')
    lines.append('')
    statuses = Counter(d['status'] for d in done)
    lines.append('## Итог')
    lines.append('')
    lines.append(f'- документов обработано: **{len(done)}**')
    for st, n in statuses.most_common():
        lines.append(f'  - `{st}` — {n}')
    if failed:
        lines.append(f'- **не удалось: {len(failed)}**')
    total_cost = sum(d['cost'] for d in done if d.get('cost'))
    lines.append(f'- стоимость по логам вызовов: **{total_cost:.2f} ₽**')
    lines.append('')

    bad = [d for d in done if d['status'] != 'ok']
    if bad:
        lines.append('## Документы не в статусе ok')
        lines.append('')
        lines.append('| документ | статус | минут | ₽ |')
        lines.append('|---|---|---|---|')
        for d in bad:
            lines.append(f'| {d["file"]} | {d["status"]} | {d["minutes"]} | {d.get("cost", "")} |')
        lines.append('')
    if failed:
        lines.append('## Не удалось обработать')
        lines.append('')
        for f in failed:
            lines.append(f'- {f}')
        lines.append('')
    lines.append('## Как продолжить')
    lines.append('')
    lines.append('```')
    lines.append('python D:\\models\\_прогон_9мес.py')
    lines.append('```')
    lines.append('')
    lines.append('Готовые артефакты пропускаются, оплаченное лежит в кэше страниц — '
                 'повтор не платит дважды.')
    open(REPORT, 'w', encoding='utf-8').write('\n'.join(lines))


def main():
    workers, timeout_min = 3, 45
    if '--workers' in sys.argv:
        workers = int(sys.argv[sys.argv.index('--workers') + 1])
    if '--timeout' in sys.argv:
        timeout_min = int(sys.argv[sys.argv.index('--timeout') + 1])
    os.makedirs(LOG, exist_ok=True)

    queue = todo_list()
    print(f'к обработке: {len(queue)} документов, воркеров {workers}, '
          f'таймаут {timeout_min} мин', flush=True)
    if not queue:
        write_report([], [], 0)
        print('всё уже обработано')
        return

    running = {}
    done, failed = [], []
    attempts = Counter()
    t0 = time.time()

    def start(name):
        log = os.path.join(LOG, f'run9_{name[:-4]}.log')
        fh = open(log, 'w', encoding='utf-8')
        p = subprocess.Popen([PY, '-X', 'utf8', '-u', os.path.join(HERE, 'pipeline.py'),
                              os.path.join(DL, name)],
                             stdout=fh, stderr=subprocess.STDOUT, cwd=HERE)
        running[p.pid] = dict(name=name, log=log, fh=fh, started=time.time(), proc=p)
        print(f'  старт: {name}', flush=True)

    while queue or running:
        while queue and len(running) < workers:
            start(queue.pop(0))
        time.sleep(5)
        for pid in list(running):
            r = running[pid]
            alive = r['proc'].poll() is None
            over = (time.time() - r['started']) > timeout_min * 60
            if alive and not over:
                continue
            if alive:
                # зависание: снимаем процесс, документ пойдёт на повтор
                r['proc'].kill()
                try:
                    r['proc'].wait(timeout=30)
                except Exception:
                    pass
                print(f'  ТАЙМАУТ: {r["name"]} (>{timeout_min} мин)', flush=True)
            r['fh'].close()
            del running[pid]
            name = r['name']
            art = os.path.join(OUT, name[:-4] + '.json')
            status = None
            if os.path.exists(art):
                try:
                    status = json.load(open(art, encoding='utf-8')).get('status')
                except Exception:
                    status = 'unreadable'
            if status:
                done.append(dict(file=name, status=status,
                                 minutes=round((time.time() - r['started']) / 60, 1),
                                 cost=log_cost(r['log'])))
                print(f'  готово: {name:<44} {status} '
                      f'{(time.time() - r["started"]) / 60:.1f} мин', flush=True)
            else:
                attempts[name] += 1
                if attempts[name] < MAX_ATTEMPTS:
                    queue.append(name)
                    print(f'  ПОВТОР: {name} (попытка {attempts[name] + 1})', flush=True)
                else:
                    failed.append(name)
                    print(f'  НЕ УДАЛОСЬ: {name}', flush=True)
            json.dump(done, open(SUMMARY, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    elapsed = time.time() - t0
    json.dump(done, open(SUMMARY, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    write_report(done, failed, elapsed)
    print()
    print(f'=== ИТОГ: {len(done)} документов за {elapsed / 3600:.1f} ч ===')
    print('  статусы:', dict(Counter(d['status'] for d in done)))
    if failed:
        print('  не удалось:', failed)
    print(f'  -> {REPORT}')


if __name__ == '__main__':
    main()