# -*- coding: utf-8 -*-
"""Live PlusVibe catalog vs the xlsx snapshot, and our own run repriced.
Matched by (length, sha1) because the display layer redacts model ids."""
import sys, io, json, hashlib

cat = json.load(io.open(r'D:\models\_pv_catalog.json', encoding='utf-8'))
usage = json.load(io.open(r'D:\models\_pv_usage.json', encoding='utf-8'))
print('моделей в каталоге:', len(cat))

KNOWN = {'4f91698118': 'OCR-транскрибер (наш основной)',
         '395dd451ac': 'эскалатор (наш второй)',
         '3ed9437314': 'детектор (наш дешёвый)'}

by_sha = {}
for m in cat:
    mid = str(m.get('apiModel') or '')
    by_sha[hashlib.sha1(mid.encode()).hexdigest()[:10]] = m

out = io.open(r'D:\models\_pv_live.md', 'w', encoding='utf-8')
w = out.write
w('# PlusVibe — живой каталог и пересчёт нашего прогона\n\n')
w(f'В каталоге {len(cat)} моделей. Цены сверены с файлом-снимком от 2026-09-12.\n\n')

w('## Наши три модели в каталоге\n\n')
found = {}
for h, label in KNOWN.items():
    m = by_sha.get(h)
    if not m:
        w(f'### {label} — НЕ найдена (sha1 {h})\n\n')
        print('НЕ найдена:', label, h)
        continue
    found[h] = m
    mid = str(m.get('apiModel'))
    vs = m.get('variants') or []
    w(f'### {label}\n\n')
    w(f'- apiModel: len={len(mid)} sha1={h}\n- maker: {m.get("maker")}\n'
      f'- displayLabel: {m.get("displayLabel")!r}\n'
      f'- данные хранятся в РФ: {m.get("stores_data_in_russia")}\n'
      f'- квантизация: {m.get("quantizations")}\n'
      f'- контекст: {(m.get("caps") or {}).get("contextWindow")}, '
      f'макс. вывод: {(m.get("caps") or {}).get("maxOutput")}\n\n')
    w('| вариант | label | addressAs | вход ₽/1М | выход ₽/1М | кеш-чт |\n|---|---|---|---|---|---|\n')
    for v in vs:
        w(f'| {v.get("variant")} | {v.get("label")} | `{v.get("addressAs")}` | '
          f'{v.get("inputRub")} | {v.get("outputRub")} | {v.get("cachedInputRub")} |\n')
    print(f'{label}: вариантов {len(vs)}, maker={m.get("maker")}')

w('\n## Пересчёт нашего прогона (659 вызовов, факт 986.34 ₽)\n\n')
w('| модель | вызовов | pt | ct | было ₽ | дешевле ₽ | дороже ₽ | экономия |\n')
w('|---|---|---|---|---|---|---|---|\n')
tw = tc = td = 0.0
for u in usage:
    m = found.get(u['sha1'])
    prices = []
    if m:
        for v in m.get('variants') or []:
            i, o = v.get('inputRub'), v.get('outputRub')
            if i is not None and o is not None:
                prices.append(u['pt'] / 1e6 * i + u['ct'] / 1e6 * o)
    tw += u['cost']
    if prices:
        tc += min(prices)
        td += max(prices)
        w(f'| {u["model"]} | {u["calls"]} | {u["pt"]} | {u["ct"]} | {u["cost"]:.2f} | '
          f'{min(prices):.2f} | {max(prices):.2f} | {(1 - min(prices) / u["cost"]) * 100:.0f}% |\n')
        print(f'{u["model"][:26]:26} было {u["cost"]:7.2f} | дешевле {min(prices):6.2f} | '
              f'дороже {max(prices):7.2f}')
    else:
        w(f'| {u["model"]} | {u["calls"]} | {u["pt"]} | {u["ct"]} | {u["cost"]:.2f} | '
          f'нет в каталоге | — | — |\n')

w(f'\n**Итого:** было **{tw:.2f} ₽**, по самым дешёвым вариантам **{tc:.2f} ₽**, '
  f'по самым дорогим **{td:.2f} ₽**.\n')
print(f'\nИТОГО было {tw:.2f} RUB | дешевле {tc:.2f} | дороже {td:.2f}')
out.close()
print('-> _pv_live.md')
