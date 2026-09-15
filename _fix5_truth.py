# -*- coding: utf-8 -*-
r"""Что на самом деле лежит в кэше эскалации ТГК-14_6мес_2025.

Вопрос: значение 11061647 — это выдумка модели или чтение ДРУГОГО поставщика?
От ответа зависит, правилен ли гейт «применять только подтверждённое текстом».
"""
import io, os, re, sys, json

sys.path.insert(0, r'D:\models')
import pipeline as P

print('активный профиль: %r' % P.ACTIVE_PROFILE)
print('поставщик в имени файла: %r' % P._provider_infix())
print('метка M_ESC: %r len=%d' % (P.model_tag(P.M_ESC), len(P.M_ESC)))
print()

PAGES = P.PAGESDIR
stem = 'ТГК-14_6мес_2025'
names = [f for f in os.listdir(PAGES)
         if f.startswith(stem) and ('_300_' in f or '_esc_' in f)]
print('=== файлы кэша (%d) ===' % len(names))
for n in sorted(names):
    p = os.path.join(PAGES, n)
    if n.endswith('.md'):
        t = io.open(p, encoding='utf-8').read()
        tn = re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', t)
        print('%-64s | 11061647:%s 11081647:%s'
              % (n[:64], 'ДА' if '11061647' in tn else 'нет',
                 'ДА' if '11081647' in tn else 'нет'))
    else:
        try:
            d = json.load(io.open(p, encoding='utf-8'))
        except Exception as e:
            print('%-64s | ошибка чтения %s' % (n[:64], e)); continue
        items = d.get('items') if isinstance(d, dict) else None
        v = None
        for it in (items or []):
            if it.get('code') == '1250':
                v = it.get('values')
        print('%-64s | 1250=%s' % (n[:64], v))
print()

# что именно вернёт код сейчас: какой файл выберет page_cache_path и cached_llm
SRC = r'D:\data-scraping\downloads'
path = None
for root, _, files in os.walk(SRC):
    for fn in files:
        if os.path.splitext(fn)[0] == stem:
            path = os.path.join(root, fn)
doc = P.pymupdf.open(path)
for pg in (1, 3):
    cp = P.page_cache_path(doc, os.path.basename(path), pg, 300, P.M_ESC)
    print('стр.%d: page_cache_path -> %s' % (pg, os.path.basename(cp)))
    print('        существует: %s' % os.path.exists(cp))
doc.close()
tag = f'{stem}_esc_balance_{P.model_tag(P.M_ESC)}{P._provider_infix()}'
llm_path = os.path.join(PAGES, '_llm_' + tag + '.json')
print('cached_llm -> %s' % os.path.basename(llm_path))
print('        существует: %s' % os.path.exists(llm_path))
