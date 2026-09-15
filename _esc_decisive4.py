# -*- coding: utf-8 -*-
r"""Тест А заново: на одну страницу бывает НЕСКОЛЬКО транскриптов (разные модели).

Прошлая версия брала по одному файлу на (документ, страница, dpi) — тот, что попался
первым в обходе каталога. Из-за этого вывод был неверным: у ТГК-14_6мес_2025 на стр.3
два транскрипта 300 dpi, в одном 11081647 (ошибка), в другом 11061647 (верно).
Теперь проверяю ВСЕ файлы и отдельно — текстовый слой самого PDF.
"""
import io, os, re, sys, json

sys.path.insert(0, r'D:\models')
import pipeline
import pymupdf

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
SRC = r'D:\data-scraping\downloads'
CACHE = re.compile(r'^(?P<stem>.+)_p(?P<p>\d+)_(?P<dpi>\d+)_(?P<rest>.+)\.md$')


def norm(t):
    return re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', t or '')


# все транскрипты: (stem, page, dpi) -> список текстов
cache = {}
for f in os.listdir(PAGES):
    m = CACHE.match(f)
    if not m:
        continue
    key = (m.group('stem'), int(m.group('p')), int(m.group('dpi')))
    cache.setdefault(key, []).append(
        norm(io.open(os.path.join(PAGES, f), encoding='utf-8').read()))


def any_dpi(stem, page, dpi, value):
    return any(value in t for t in cache.get((stem, page, dpi), []))


pdf_cache = {}


def text_layer(stem, page):
    """текстовый слой PDF, если файл найден"""
    if stem not in pdf_cache:
        found = None
        for root, _, files in os.walk(SRC):
            for fn in files:
                if os.path.splitext(fn)[0] == stem:
                    found = os.path.join(root, fn)
        pdf_cache[stem] = found
    path = pdf_cache[stem]
    if not path:
        return None
    d = pymupdf.open(path)
    try:
        if page > d.page_count:
            return None
        return norm(d[page - 1].get_text())
    finally:
        d.close()


print('=== ТЕСТ А (переделан): видно ли правильное значение на 200 dpi ===')
print('для каждой строки, которую эскалация исправила: ищем НОВОЕ значение')
print()
for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    warns = doc.get('warnings') or []
    for form in ('balance', 'income_statement', 'cash_flow'):
        live = [w for w in warns if w.startswith(form + ':') and re.search(
            r'fixed by escalation|did not fully reconcile|эскалация отклонена', w)]
        if not live:
            continue
        d = doc.get(form) or {}
        tp = [p for p in (d.get('transcript_pages') or []) if isinstance(p, int)][:8]
        for it in (d.get('items') or []):
            if not it.get('corrected_by'):
                continue
            old = it.get('values_ocr1') or []
            new = it.get('values') or []
            for i, (o, n) in enumerate(zip(old, new)):
                if o == n or n is None:
                    continue
                dn = re.sub(r'\D', '', str(n))
                do = re.sub(r'\D', '', str(o)) if o is not None else ''
                if not dn:
                    continue
                w200 = [p for p in tp if any_dpi(stem, p, 200, dn)]
                w300 = [p for p in tp if any_dpi(stem, p, 300, dn)]
                o200 = [p for p in tp if do and any_dpi(stem, p, 200, do)]
                lay = [p for p in tp
                       if (text_layer(stem, p) or '').find(dn) >= 0]
                print('%s  %s  код %s  кол.%d' % (stem, form, it.get('code'), i))
                print('   было %s -> стало %s' % (o, n))
                print('   верное значение: 200 dpi %s | 300 dpi %s | текстовый слой %s'
                      % (w200 or 'НЕТ', w300 or 'НЕТ', lay or 'НЕТ'))
                print('   ошибочное значение на 200 dpi: %s' % (o200 or 'НЕТ'))
                print('   есть ли транскрипт 200 dpi вообще: %s'
                      % ('да' if any((stem, p, 200) in cache for p in tp) else 'НЕТ'))
