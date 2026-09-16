# -*- coding: utf-8 -*-
r"""Масштаб класса «страница выбрана детекцией, но прочитана не полностью» (0 ₽).

Гипотеза, проверяемая здесь. Артефакт «ИПС_6мес_2025» держит transcript_pages = [1,2,3,4,5],
статус ok и ни одного предупреждения — а транскрипта плюсвайба для стр. 4 нет вовсе. Причина
видна в коде: при `finish_reason=content_filter` transcribe_cached возвращает ОБРЕЗАННЫЙ текст,
намеренно не кладёт его в кэш и НЕ пишет предупреждение. Форма собирается из неполной страницы,
проверка `form_is_complete` этого не видит (замыкающий код стоит на другой странице), а кэш не
появляется — значит по одному факту отсутствия файла можно найти все такие случаи.

Здесь по каждому артефакту пилота сверяется: для каждой страницы формы есть ли транскрипт
ТОГО ЖЕ поставщика. Файлов не создаётся, моделей не зовётся.
"""
import glob
import io
import json
import os
import re
import sys

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
FORMS = ('balance', 'income_statement', 'cash_flow')


def have_pages(stem, provider):
    """{page: [имена файлов]} по всем транскриптам документа.

    Суффикс поставщика берётся из профиля (cache_suffix), а не из первых букв имени: у
    plusvibe это '_pv', а не '_pl' — на этой ошибке первый прогон этого скрипта объявил
    «89 форм без транскриптов», что было дефектом измерителя, а не находкой.
    """
    try:
        import sys as _s
        if r'D:\models' not in _s.path:
            _s.path.insert(0, r'D:\models')
        import providers as PV
        suffix = PV.load_profile(provider).cache_suffix
    except Exception:
        suffix = {'plusvibe': '_pv', 'polza': ''}.get(provider, '')
    out = {}
    for f in glob.glob(os.path.join(PAGES, f'{stem}_p*_*.md')):
        m = re.search(r'_p(\d+)_(\d+)_', os.path.basename(f))
        if not m:
            continue
        base = os.path.basename(f)
        if suffix:
            if f'{suffix}_' not in base:
                continue
        elif re.search(r'_[a-z]{2}_[0-9a-f]{10}\.md$', base):
            continue   # чужой поставщик (у polza суффикса нет)
        out.setdefault(int(m.group(1)), []).append(base)
    return out


rows = []
text_layer_docs = []
for path in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(path)
    if b.startswith('_'):
        continue
    try:
        j = json.load(io.open(path, encoding='utf-8'))
    except Exception:
        continue
    stem = b[:-5]
    src = j.get('source') or {}
    if src.get('text_layer'):
        # Документ собран из ТЕКСТОВОГО СЛОЯ: страницы не читаются моделью вовсе, файлов
        # кэша и не должно быть. Отдельная находка: артефакт при этом записывает
        # provider=plusvibe и ocr_model=gemini, хотя модель эти страницы не читала.
        text_layer_docs.append(stem)
        continue
    prov = src.get('provider') or 'polza'
    files = have_pages(stem, prov)
    for fk in FORMS:
        d = j.get(fk) or {}
        plist = d.get('transcript_pages') or []
        if not plist:
            continue
        missing = [p for p in plist if p not in files]
        if missing:
            rows.append((stem, fk, prov, plist, missing, j.get('status')))

print(f'артефактов проверено: '
      f'{len([f for f in glob.glob(os.path.join(EX, "*.json")) if not os.path.basename(f).startswith("_")])}')
print(f'из них из текстового слоя (страницы моделью не читались): {len(text_layer_docs)} '
      f'— {text_layer_docs}')
print(f'форм со сканами, где часть страниц НЕ прочитана: {len(rows)}')
print()
full_missing = 0
for stem, fk, prov, plist, missing, status in rows:
    if len(missing) == len(plist):
        full_missing += 1
    print(f'{stem[:40]:40} {fk[:12]:12} {prov:9} status={status}')
    print(f'    страницы в артефакте: {plist}')
    print(f'    НЕТ транскрипта:      {missing}   (из {len(plist)})')
print()
print(f'форм, где не прочитана ВСЯ форма: {full_missing}')
print(f'форм, где не прочитана ЧАСТЬ страниц: {len(rows) - full_missing}')
