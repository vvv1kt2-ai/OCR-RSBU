# -*- coding: utf-8 -*-
r"""Происхождение артефактов, собранных из текстового слоя (0 ₽).

Находка, которую надо либо подтвердить, либо снять. У 16 артефактов пилота файлов кэша
страниц нет вовсе — они собраны из ТЕКСТОВОГО СЛОЯ, модели страницы не читали. При этом
collect_scan_results безусловно пишет в source: ocr_model = M_MAIN и provider = имя активного
профиля. Для текстовой ветки это ЛОЖЬ ПРОИСХОЖДЕНИЯ: артефакт утверждает, что страницы
прочитала модель google/gemini-3.8-flash у plusvibe, хотя модель не вызывалась.

Почему это важно, а не косметика. Цена, качество и воспроизводимость у поставщиков разные
(plusvibe против polza расходились в 12 раз по цене), и на эти поля опирается разбор
«откуда взялось значение». Замер цены пилота считается по ролям моделей; если артефакт
приписывает себе вызовы, которых не было, то и любая сверка «сколько раз звали main» по
артефактам неверна.

Здесь печатается только сводка: сколько артефактов из слоя, что у них в source, и есть ли
среди них такие, где модель всё-таки звалась (тогда поле не ложное).
"""
import glob
import io
import json
import os

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

rows = []
for p in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(p)
    if b.startswith('_'):
        continue
    j = json.load(io.open(p, encoding='utf-8'))
    src = j.get('source') or {}
    stem = b[:-5]
    ncache = len(glob.glob(os.path.join(PAGES, stem + '_p*.md')))
    rows.append(dict(stem=stem, text_layer=bool(src.get('text_layer')),
                     provider=src.get('provider'), model=src.get('ocr_model'),
                     ncache=ncache, status=j.get('status')))

print('артефактов:', len(rows))
tl = [r for r in rows if r['text_layer']]
sc = [r for r in rows if not r['text_layer']]
print(f'из текстового слоя: {len(tl)}')
print(f'со сканов:          {len(sc)}')
print()
print('--- артефакты из текстового слоя: что записано в source ---')
for r in tl:
    print(f"{r['stem'][:38]:38} provider={str(r['provider']):9} model={'задан' if r['model'] else 'ПУСТО':6} "
          f"кэш-файлов={r['ncache']:3} status={r['status']}")
print()
noprov = [r for r in tl if not r['provider']]
print(f'из них без поставщика в source: {len(noprov)}')
print(f'из них с непустым кэшем страниц (модель всё-таки звалась): '
      f'{len([r for r in tl if r["ncache"]])}')
print()
print('--- со сканов: есть ли артефакты вообще без кэша ---')
nocache = [r for r in sc if not r['ncache']]
print(f'со сканов и без единого файла кэша: {len(nocache)} — {[r["stem"] for r in nocache]}')
