# -*- coding: utf-8 -*-
r"""Снижение эскалации до 200 dpi: СЭКОНОМИТ ЛИ ЭТО ЧТО-НИБУДЬ?

Сомнение не праздное. По прежним наблюдениям у anthropic-канала (роль esc) одно и то же
изображение считалось за 85 входных токенов, тогда как у основной модели — за 1142. Если
картиночные токены у esc в статистику не попадают, то уменьшение картинки вдвое по площади
может не изменить цену вообще — и тогда снижать dpi бессмысленно, а качество мы потеряем.

Здесь прямой опыт: одна и та же страница читается ролью esc на 200 и на 300 dpi, и
сравниваются prompt_tokens / completion_tokens / цена. Кэш не трогается (зовём chat напрямую),
страница выбрана из тех, что эскалация реально перечитывала.

Стоимость опыта: два вызова esc, ориентировочно 1–2 ₽.
"""
import io
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402
import pymupdf  # noqa: E402

DOC = 'ТГК-14_6мес_2025'
PDF = None
for root in (r'D:\data-scraping\downloads',):
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith('.pdf') and os.path.splitext(f)[0] == DOC:
                PDF = os.path.join(dirpath, f)
if not PDF:
    print('PDF не найден'); sys.exit(1)

PAGE = 3   # нативный dpi 207; на 200 dpi оба поставщика прочитали 11081647 верно
print(f'документ: {DOC}, страница {PAGE}')
print(f'роль esc: длина имени модели {len(P.M_ESC)}, main {len(P.M_MAIN)}')
print()

doc = pymupdf.open(PDF)
res = {}
for dpi in (200, 300):
    png = P.render_png(doc[PAGE - 1], dpi)
    raw = len(png) * 3 // 4          # примерный размер PNG в байтах из base64
    msg = [P.img_message(png, P.TRANSCRIBE_PROMPT + f' (страница {PAGE} файла)')]
    before = dict(P.USAGE)
    try:
        txt, fin = P.chat(msg, P.M_ESC, max_tokens=16000)
    except Exception as e:
        print(f'{dpi} dpi: вызов не удался — {e}')
        continue
    d_pt = P.USAGE['prompt'] - before['prompt']
    d_ct = P.USAGE['completion'] - before['completion']
    d_cost = P.USAGE['cost_rub'] - before['cost_rub']
    res[dpi] = {'pt': d_pt, 'ct': d_ct, 'cost': d_cost, 'png': raw, 'fin': fin,
                'chars': len(txt)}
    print(f'{dpi} dpi: PNG ~{raw/1024:.0f} КБ  pt={d_pt}  ct={d_ct}  '
          f'цена={d_cost:.4f} ₽  finish={fin}  знаков ответа={len(txt)}')
    # ключевое число из ответа — то, что решает арифметика
    has_ok = '11 081 647' in txt or '11081647' in txt
    has_bad = '11 061 647' in txt or '11061647' in txt
    print(f'        прочитано 11081647 (верное): {has_ok};  11061647 (ошибка): {has_bad}')
doc.close()

if len(res) == 2:
    r2, r3 = res[200], res[300]
    print()
    print('=== ИТОГ')
    print(f'  площадь картинки: 200 dpi = {r2["png"]/1024:.0f} КБ, '
          f'300 dpi = {r3["png"]/1024:.0f} КБ (в {r3["png"]/max(r2["png"],1):.2f} раза больше)')
    print(f'  входные токены:   {r2["pt"]} -> {r3["pt"]}')
    print(f'  цена:             {r2["cost"]:.4f} -> {r3["cost"]:.4f} ₽')
    if r3['cost'] > 0:
        print(f'  экономия на снижении до 200 dpi: '
              f'{100.0 * (r3["cost"] - r2["cost"]) / r3["cost"]:.1f}%')
    if abs(r3['cost'] - r2['cost']) < 0.01 * max(r3['cost'], 1e-9):
        print('  ВНИМАНИЕ: цена не изменилась — снижение dpi не экономит, '
              'картиночные токены у этой роли в цену не входят')
