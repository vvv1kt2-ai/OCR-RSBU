# -*- coding: utf-8 -*-
r"""Разбор отказов HTTP 400 по данным поставщика: какой ИМЕННО вызов он отвергает.

Гипотеза «тело запроса слишком велико» проверена живым опытом и НЕ подтвердилась: страница
300 dpi даёт тело 3.6–4.1 МБ, и такие вызовы проходят. Значит дело в чём-то другом, и гадать
не надо — в логе поставщика у каждого вызова есть prompt_tokens, completion_tokens и
latency_ms. По ним отказы разделяются на типы:

  * мало входных токенов (~85) — это вызов с ОДНИМ изображением: поставщик считает картинку
    отдельно, поэтому текст промпта мал;
  * много входных токенов (тысячи) — это вызов со СТЕНАГРАММОЙ ТЕКСТА: структурирование
    расшифровки после эскалации.

Если все 400 собрались в одном типе, причина локальна и лечится в одном месте.
Печатаем: роль, число входных токенов, задержку — по каждому отказу и в сравнении с успехом.
"""
import io, json, collections, statistics

SRC = r'D:\models\plusvibe-usage.ndjson'
MAIN_PREFIX = 'gemini-3.8-flash'
DETECT_PREFIX = 'deepseek-v4.1-flash'


def role(m):
    if m.startswith(MAIN_PREFIX):
        return 'main'
    if m.startswith(DETECT_PREFIX):
        return 'detect'
    return 'esc'


rows = collections.defaultdict(lambda: collections.defaultdict(list))
with io.open(SRC, encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        k = role(r.get('model') or '')
        s = r.get('status')
        rows[k][s].append((int(r.get('prompt_tokens') or 0),
                           int(r.get('completion_tokens') or 0),
                           int(r.get('latency_ms') or 0)))

print('=== почему отказы: сравнение входных токенов у успеха и у отказа')
print('  %-8s %-6s %7s %14s %14s %12s' % ('роль', 'статус', 'шт.', 'вход p50', 'вход max', 'задержка p50'))
for k in ('main', 'esc', 'detect'):
    for s in (200, 400, 503, 504, 502):
        v = rows[k].get(s)
        if not v:
            continue
        pts = sorted(x[0] for x in v)
        lats = sorted(x[2] for x in v)
        print('  %-8s %-6s %7d %14d %14d %12d'
              % (k, s, len(v), pts[len(pts) // 2], pts[-1], lats[len(lats) // 2]))

print()
print('=== отказы 400 по ролям: распределение входных токенов')
for k in ('main', 'esc'):
    v = rows[k].get(400) or []
    if not v:
        continue
    pts = sorted(x[0] for x in v)
    small = [p for p in pts if p < 500]
    big = [p for p in pts if p >= 500]
    print('  %-8s всего %d: с картинкой (вход <500) %d, с текстом (вход >=500) %d'
          % (k, len(v), len(small), len(big)))
    if big:
        print('        текстовые: вход %s' % big[:8])
    if small:
        print('        картиночные: вход %s' % small[:8])
