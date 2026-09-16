# -*- coding: utf-8 -*-
r"""Насколько повторяются ДУБЛИ КОДОВ в формах? Замер по кэшу транскриптов, без LLM.

Вопрос пользователя: «не уверен, что их может быть больше и что будет повторение в будущем».
Отвечать надо замером, а не догадкой. Смотрим все транскрипты страниц (200 dpi — это то, что
читает основная модель) и ищем файлы, где 4-значный код встречается дважды в колонке кода.

Дубль в артефакте увидеть нельзя: конвейер второй строки просто не оставляет. Поэтому смотрим
СЫРЬЁ — транскрипт страницы, где напечатано как в отчёте.

Чего НЕ делаем: не считаем это ошибкой чтения. Дубль кода — свойство самого отчёта
(у «Моторных» 1250 напечатан дважды: «Денежные средства» 4 070 и «Депозитные счета» 14 500).
"""
import io, os, re, glob, collections

PAGES = r'D:\models\extracted\pages'
CELL_CODE = re.compile(r'\|\s*(\d{4})\s*\|')

# берём по одному транскрипту на (документ, страница): слой 200 dpi, любая модель
best = {}
for f in glob.glob(os.path.join(PAGES, '*_p*_200_*.md')):
    b = os.path.basename(f)
    m = re.match(r'^(?P<doc>.+)_p(?P<page>\d+)_200_.*\.md$', b)
    if not m:
        continue
    key = (m.group('doc'), int(m.group('page')))
    best.setdefault(key, f)

print('транскриптов 200 dpi: %d, уникальных (документ, страница): %d' % (
    len(glob.glob(os.path.join(PAGES, '*_p*_200_*.md'))), len(best)))

dup_files = 0
by_code = collections.Counter()
docs = collections.defaultdict(set)
detail = []
for (doc, page), f in sorted(best.items()):
    try:
        txt = io.open(f, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    codes = CELL_CODE.findall(txt)
    c = collections.Counter(codes)
    d = {k: v for k, v in c.items() if v >= 2}
    if not d:
        continue
    dup_files += 1
    for k, v in d.items():
        by_code[k] += 1
        docs[doc].add(k)
    detail.append((doc, page, sorted(d.items())))

print('страниц с дублем кода: %d из %d (%.1f%%)' % (dup_files, len(best),
                                                    100.0 * dup_files / max(1, len(best))))
print('документов затронуто: %d' % len(docs))
print()
print('=== какие коды дублируются (код: сколько страниц)')
for k, v in by_code.most_common(15):
    print('   %s: %d' % (k, v))
print()
print('=== по документам (первые 20)')
for doc in sorted(docs, key=lambda x: -len(docs[x]))[:20]:
    print('   %-42s %s' % (doc[:42], sorted(docs[doc])))
print()
print('=== страницы (первые 12)')
for doc, page, d in detail[:12]:
    print('   %-40s стр.%-4d %s' % (doc[:40], page, d))
