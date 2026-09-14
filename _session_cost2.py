# -*- coding: utf-8 -*-
r"""Фактический расход по счетам PlusVibe: сколько стоила и работа скриптов, и агент.

В журнале расхода есть записи с ценой. Если вызовы агента идут через тот же счёт,
они там тоже есть — тогда видно, во что обошлась сама сессия, а не только скрипты.
Считается по отпечаткам моделей: вывод подменяет идентификаторы пустой строкой.
"""
import io, json, os, hashlib
from collections import defaultdict

CAND = [r'D:\models\_pv_usage.json', r'D:\models\_pv_usage_agent.json',
        r'D:\models\_polza_usage.json']


def load(path):
    try:
        d = json.load(io.open(path, encoding='utf-8'))
    except Exception as e:
        return None, str(e)
    rows = d.get('rows') if isinstance(d, dict) else d
    return rows, None


for path in CAND:
    if not os.path.exists(path):
        print('%s — нет файла' % os.path.basename(path))
        continue
    rows, err = load(path)
    if err:
        print('%s — ошибка: %s' % (os.path.basename(path), err))
        continue
    if not isinstance(rows, list):
        print('%s — неожиданная структура: %s' % (os.path.basename(path), type(rows).__name__))
        continue
    print('=== %s ===' % os.path.basename(path))
    print('  записей: %d' % len(rows))
    if not rows:
        continue
    print('  поля записи: %s' % sorted(rows[0].keys()))
    total = 0.0
    bymodel = defaultdict(lambda: {'n': 0, 'cost': 0.0, 'in': 0, 'out': 0, 'reason': 0})
    times = []
    for r in rows:
        c = r.get('cost')
        try:
            c = float(c or 0)
        except (TypeError, ValueError):
            c = 0.0
        total += c
        name = str(r.get('model') or r.get('modelName') or r.get('name') or '')
        m = bymodel[(len(name), hashlib.sha1(name.encode('utf-8')).hexdigest()[:10])]
        m['n'] += 1
        m['cost'] += c
        for k, dst in (('prompt_tokens', 'in'), ('completion_tokens', 'out'),
                       ('reasoning_tokens', 'reason')):
            v = r.get(k)
            if isinstance(v, (int, float)):
                m[dst] += v
        for tk in ('createdAt', 'created_at', 'time', 'date', 'timestamp'):
            if r.get(tk):
                times.append(str(r[tk])[:19])
                break
    print('  сумма по счетам: %.2f ₽' % total)
    if times:
        print('  период: %s ... %s' % (min(times), max(times)))
    print('  по моделям (len имени, sha1):')
    for (ln, h), m in sorted(bymodel.items(), key=lambda kv: -kv[1]['cost']):
        print('    len=%-3d %s  вызовов %5d  %.2f ₽  вход %9d  выход %8d  рассужд %8d'
              % (ln, h, m['n'], m['cost'], m['in'], m['out'], m['reason']))
    print()
