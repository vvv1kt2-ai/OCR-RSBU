# -*- coding: utf-8 -*-
"""Identity / cross-year integrity check for extracted results.

Detectors, all of which fired on defect 4.1:

  A. esc-artifact year: the escalation artifact of a `*_6мес_YYYY` document must carry
     columns for that year. A mismatch means the artifact holds another document's page.
  B. cross-year consistency: the same emitter's 2025 and 2026 files both carry the column
     "На 31 декабря 2024 г."; those two values must be equal. A contradiction is either an
     extraction error in one of them or foreign data in one of them.
  C. orphan page cache: a `{doc}_p{n}_{dpi}_{model}.md` transcript whose `{doc}` is no
     document of the corpus cannot belong to anyone — the fingerprint of a shared key.
  D. model identity in the cache key: page transcripts must say which model wrote them.

Writes `_identity_check.md`. Read-only over `extracted/`.
"""
import os, re, json, glob, collections, datetime

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
DOWNLOADS = r'D:\data-scraping\downloads'
FORMS = ('balance', 'income_statement', 'cash_flow')

MONTHS = {'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
          'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12}

docs = {}
for f in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(f)
    if b.startswith('_'):
        continue
    docs[b[:-5]] = json.load(open(f, encoding='utf-8'))


def date_key(label):
    """'На 31 декабря 2024 г.' -> '2024-12-31'; 'На 30 июня 2025 г.' -> '2025-06-30'."""
    s = re.sub(r'\s+', ' ', str(label)).strip()
    m = re.search(r'(\d{1,2})\s+([А-Яа-яЁё]+)\s+(\d{4})', s)
    if m and m.group(2).lower() in MONTHS:
        return '%s-%02d-%02d' % (m.group(3), MONTHS[m.group(2).lower()], int(m.group(1)))
    m = re.search(r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})', s)
    if m:
        return '%s-%02d-%02d' % (m.group(3), int(m.group(2)), int(m.group(1)))
    return None


def dates(res):
    out = {}
    for i, c in enumerate((res or {}).get('columns') or []):
        k = date_key(c)
        if k:
            out.setdefault(k, i)
    return out


def rows(res):
    out = {}
    for it in (res or {}).get('items') or []:
        for rec in [it] + (it.get('children') or []):
            out.setdefault((rec.get('code'), (rec.get('name') or '').strip()), rec)
    return out


L = ['# Проверка идентичности результатов\n',
     'Дата прогона: %s\n' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')]

# ---------- A ----------
L.append('\n## A. Артефакты эскалации: год колонок против года файла\n')
L.append('| артефакт | год файла | годы колонок | вердикт |')
L.append('|---|---|---|---|')
badA = []
for f in sorted(glob.glob(os.path.join(PAGES, '*_esc_*.json'))):
    b = os.path.basename(f)
    d = json.load(open(f, encoding='utf-8'))
    m = re.search(r'_6мес_(\d{4})', b)
    want = m.group(1) if m else '?'
    years = sorted({date_key(c)[:4] for c in ((d.get('columns') or [])) if date_key(c)})
    got = years[-1] if years else '?'
    ok = (want == '?' or got == '?' or want == got)
    if not ok:
        badA.append(b)
    L.append('| %s | %s | %s | %s |' % (b, want, ','.join(years) or '?',
                                        'ok' if ok else '**ЧУЖОЙ ДОКУМЕНТ?**'))
L.append('\nНарушений: **%d**\n' % len(badA))

# ---------- B ----------
L.append('\n## B. Один эмитент, два года: совпадающие даты должны совпадать\n')
by_emitter = collections.defaultdict(dict)
for key in docs:
    m = re.match(r'^(.*)_6мес_(\d{4})$', key)
    if m:
        by_emitter[m.group(1)][m.group(2)] = key
L.append('| эмитент | форма | код | строка | дата | 2025-файл | 2026-файл | вердикт |')
L.append('|---|---|---|---|---|---|---|---|')
badB = 0
per_emitter = collections.Counter()
for emitter, years in sorted(by_emitter.items()):
    if '2025' not in years or '2026' not in years:
        continue
    a, b = docs[years['2025']], docs[years['2026']]
    for form in FORMS:
        da, db = dates(a.get(form)), dates(b.get(form))
        ra, rb = rows(a.get(form)), rows(b.get(form))
        for (code, name) in sorted(set(ra) & set(rb), key=lambda x: (str(x[0]), x[1])):
            for dkey in sorted(set(da) & set(db)):
                va = (ra[(code, name)].get('values') or [])
                vb = (rb[(code, name)].get('values') or [])
                x, y = da[dkey], db[dkey]
                if len(va) <= x or len(vb) <= y:
                    continue
                if va[x] is None or vb[y] is None or va[x] == vb[y]:
                    continue
                badB += 1
                per_emitter[emitter] += 1
                L.append('| %s | %s | %s | %s | %s | %s | %s | **РАСХОЖДЕНИЕ** |' % (
                    emitter, form, code, name[:28], dkey, va[x], vb[y]))
L.append('\nРасхождений: **%d**\n' % badB)
L.append('\nПо эмитентам: ' + ', '.join('%s %d' % (k, v) for k, v in per_emitter.most_common()) + '\n')

# ---------- C / D ----------
# two key shapes: the legacy one (no fingerprint) and the current one
# `{stem}_p{p}_{dpi}_{model}.md` and `{stem}_p{p}_{dpi}_{model}_{sha1[:10]}.md`.
# For the current shape, {model} must not swallow the fingerprint: everything after the
# dpi is split at the LAST underscore.
page_new = re.compile(r'^(?P<doc>.+?)_p(?P<p>\d+)_(?P<dpi>200|300)_(?P<rest>.+)\.md$')
FP = re.compile(r'^[0-9a-f]{10}$')


def split_key(name):
    """-> (doc, page, dpi, model, fingerprint_or_None), or None if not a page transcript"""
    m = page_new.match(name)
    if not m:
        return None
    rest = m.group('rest')
    fp = None
    if '_' in rest:
        head, tail = rest.rsplit('_', 1)
        if FP.match(tail):
            rest, fp = head, tail
    return m.group('doc'), m.group('p'), m.group('dpi'), rest, fp


known = set(docs)
dl = {os.path.splitext(n)[0] for n in os.listdir(DOWNLOADS)} if os.path.isdir(DOWNLOADS) else set()
orphans = collections.Counter()
models = collections.Counter()
with_fp = 0
without_fp = 0
for n in sorted(os.listdir(PAGES)):
    if not os.path.isfile(os.path.join(PAGES, n)) or not n.endswith('.md'):
        continue
    parts = split_key(n)
    if not parts:
        continue
    doc, _p, _dpi, model, fp = parts
    models[model] += 1
    if fp:
        with_fp += 1
    else:
        without_fp += 1
    if doc not in known and doc not in dl:
        orphans[(doc, model)] += 1

L.append('\n## C. Кэш страниц без владельца\n')
L.append('| префикс имени | модель в имени | файлов |')
L.append('|---|---|---|')
for (doc, model), n in sorted(orphans.items()):
    L.append('| %s | `%s` | %d |' % (doc, model or '(пусто)', n))
L.append('\nПрефиксов без владельца: **%d** (файлов: %d)\n' % (len(orphans), sum(orphans.values())))

L.append('\n## D. Идентичность модели и файла в ключе кэша страниц\n')
L.append('Отчёт намеренно числовой: среда отображения подменяет идентификаторы моделей '
         'пустой строкой, поэтому имена здесь не печатаются, только длины и количества.\n')
L.append('| длина метки модели | файлов |')
L.append('|---|---|')
len_counts = collections.Counter(len(m) for m, n in models.items() for _ in range(n))
for ln, n in sorted(len_counts.items()):
    L.append('| %d | %d |' % (ln, n))
empty_tag = sum(n for m, n in models.items() if not m)
L.append('\nМеток нулевой длины (модель не различима): **%d**\n' % empty_tag)
L.append('С отпечатком PDF: **%d**; без отпечатка (старый ключ): **%d**\n'
         % (with_fp, without_fp))

open(os.path.join(r'D:\models\_identity_check.md'), 'w', encoding='utf-8').write('\n'.join(L))
print('A. esc artifacts with wrong year :', len(badA), badA)
print('B. cross-year contradictions     :', badB)
print('   per emitter:', dict(per_emitter))
print('C. orphan cache prefixes         :', len(orphans), 'files:', sum(orphans.values()), dict(orphans))
print('D. page cache: files with fingerprint =', with_fp, '| legacy =', without_fp,
      '| distinct model tags =', len(models),
      '| tags of length 0 =', sum(n for m, n in models.items() if not m),
      '| tag length -> count =', dict(sorted(len_counts.items())))
print('report -> D:\\models\\_identity_check.md')
