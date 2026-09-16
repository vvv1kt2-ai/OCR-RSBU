# -*- coding: utf-8 -*-
r"""Влияет ли разрешение картинки на ЦЕНУ у роли esc?

Прошлый опыт был испорчен: цена вызова почти целиком состоит из выходных токенов (14333 шт
= 4.51 ₽), и на этом фоне разница по картинке не видна. Здесь наоборот: ответ просим
минимальный (одно слово), поэтому цена вызова ≈ цена картинки. Сравниваем 200 и 300 dpi на
одной странице.

Если цена не изменится — снижение эскалации до 200 dpi не экономит ничего, потому что
картиночные токены anthropic-канала в счёт не идут (в логе у esc входные токены 160 при
любом разрешении, тогда как у gemini-3.8-flash — 1184).

Кэш не трогаем. Опыт дешёвый: ответ в одно слово.
"""
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402
import pymupdf  # noqa: E402

DOC = 'ТГК-14_6мес_2025'
PAGE = 3
ASK = 'Ответь ровно одним словом, без пояснений: это бухгалтерский баланс?'

PDF = None
for dirpath, _, files in os.walk(r'D:\data-scraping\downloads'):
    for f in files:
        if f.lower().endswith('.pdf') and os.path.splitext(f)[0] == DOC:
            PDF = os.path.join(dirpath, f)
if not PDF:
    print('PDF не найден'); sys.exit(1)

doc = pymupdf.open(PDF)
print(f'{DOC}, страница {PAGE}; ответ просим в одно слово, чтобы цена вызова '
      f'определялась картинкой')
print()
res = {}
for dpi in (200, 300):
    png = P.render_png(doc[PAGE - 1], dpi)
    kb = len(png) * 3 // 4 / 1024
    msg = [P.img_message(png, ASK)]
    before = dict(P.USAGE)
    try:
        txt, fin = P.chat(msg, P.M_ESC, max_tokens=200)
    except Exception as e:
        print(f'{dpi} dpi: не удался — {str(e)[:90]}')
        continue
    d = {'pt': P.USAGE['prompt'] - before['prompt'],
         'ct': P.USAGE['completion'] - before['completion'],
         'cost': P.USAGE['cost_rub'] - before['cost_rub'],
         'kb': kb, 'txt': txt.strip()[:40], 'fin': fin}
    res[dpi] = d
    print(f"{dpi} dpi: PNG ~{kb:.0f} КБ  pt={d['pt']}  ct={d['ct']}  "
          f"цена={d['cost']:.5f} ₽  finish={fin}  ответ={d['txt']!r}")
doc.close()

print()
if len(res) == 2:
    a, b = res[200], res[300]
    print('=== ИТОГ по роли esc')
    print(f'  картинка выросла: {a["kb"]:.0f} -> {b["kb"]:.0f} КБ (в {b["kb"]/a["kb"]:.2f} раза)')
    print(f'  входные токены:   {a["pt"]} -> {b["pt"]}')
    print(f'  цена:             {a["cost"]:.5f} -> {b["cost"]:.5f} ₽')
    if abs(b['cost'] - a['cost']) <= 0.02 * max(b['cost'], 1e-9):
        print('  ВЫВОД: цена не зависит от разрешения — снижение до 200 dpi НЕ экономит')
    else:
        print(f'  ВЫВОД: цена зависит от разрешения, экономия '
              f'{100*(b["cost"]-a["cost"])/b["cost"]:.0f}%')
else:
    print('=== опыт неполный: не удалось получить обе точки')
