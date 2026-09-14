# -*- coding: utf-8 -*-
r"""Migrate existing page transcripts to the new cache key (adds the PDF fingerprint).

The key changed from `{stem}_p{p}_{dpi}_{tag}.md` to `{stem}_p{p}_{dpi}_{tag}_{fp}.md`.
Without migration every cached page misses and a rerun pays for all of them again.
The stem identifies the document and the fingerprint is derived from the matching PDF,
so the rename is exact — no transcription is redone, nothing is deleted.

    python _migrate_cache_keys.py            # dry run
    python _migrate_cache_keys.py --apply    # rename
"""
import os, re, sys, json

sys.path.insert(0, r'D:\models')
import pipeline as P

APPLY = '--apply' in sys.argv
PAGES = os.path.join(P.OUTDIR, 'pages')
DOWNLOADS = P.DOWNLOADS

OLD = re.compile(r'^(?P<stem>.+?)_p(?P<p>\d+)_(?P<dpi>200|300)_(?P<tag>[^_]*[a-z0-9-]+)\.md$')

pdfs = {}
for n in os.listdir(DOWNLOADS):
    if n.lower().endswith('.pdf'):
        pdfs[os.path.splitext(n)[0]] = os.path.join(DOWNLOADS, n)


def fingerprint(path):
    import hashlib
    h = hashlib.sha1()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:10]


plan, skip = [], []
fp_cache = {}
for n in sorted(os.listdir(PAGES)):
    src = os.path.join(PAGES, n)
    if not os.path.isfile(src) or not n.endswith('.md'):
        continue
    m = OLD.match(n)
    if not m:
        skip.append((n, 'не подходит под старый ключ'))
        continue
    stem = m.group('stem')
    pdf = pdfs.get(stem)
    if not pdf:
        skip.append((n, 'нет PDF с таким именем'))
        continue
    if stem not in fp_cache:
        fp_cache[stem] = fingerprint(pdf)
    new = '%s_p%s_%s_%s_%s.md' % (stem, m.group('p'), m.group('dpi'), m.group('tag'), fp_cache[stem])
    if new == n:
        skip.append((n, 'уже в новом виде'))
        continue
    plan.append((n, new))

print('к переименованию: %d' % len(plan))
print('пропущено       : %d' % len(skip))
for n, why in skip[:10]:
    print('   skip %-46s %s' % (n.encode('unicode_escape').decode()[:46], why))

print('\nпримеры:')
for a, b in plan[:5]:
    print('   %s' % a.encode('unicode_escape').decode())
    print('   -> %s' % b.encode('unicode_escape').decode())

collide = [(a, b) for a, b in plan if os.path.exists(os.path.join(PAGES, b))]
print('\nколлизий с существующими файлами: %d' % len(collide))
for a, b in collide[:5]:
    print('   %s -> %s (уже есть)' % (a.encode('unicode_escape').decode(), b.encode('unicode_escape').decode()))

if APPLY:
    done = 0
    for a, b in plan:
        dst = os.path.join(PAGES, b)
        if os.path.exists(dst):
            continue
        os.rename(os.path.join(PAGES, a), dst)
        done += 1
    print('\nпереименовано: %d' % done)
    log = {'renamed': done, 'plan': [{'from': a, 'to': b} for a, b in plan]}
    json.dump(log, open(r'D:\models\_migrate_cache_keys.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('журнал -> D:\\models\\_migrate_cache_keys.json')
else:
    print('\nDRY RUN — ничего не изменено. Запустить с --apply')
