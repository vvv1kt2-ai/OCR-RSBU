# -*- coding: utf-8 -*-
r"""Проверка отката подсказки детекции: текст совпал, кэш переиспользуется."""
import hashlib, io, os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

ORIG_SHA = '7371b87364b2'
h = hashlib.sha1(P.DETECT_PROMPT.encode('utf-8')).hexdigest()[:12]
print('текст подсказки: длина %d, sha1 %s' % (len(P.DETECT_PROMPT), h))
print('совпадает с исходным (%s): %s' % (ORIG_SHA, 'ДА' if h == ORIG_SHA else 'НЕТ'))
print('подсказка содержит notes/audit: %s'
      % ('да' if ('notes' in P.DETECT_PROMPT or 'audit' in P.DETECT_PROMPT) else 'нет (как и было)'))
print()
print('ключ кэша детекции:')
print('   для документа: %r' % P.detect_cache_stem('ТГК-14_6мес_2025.pdf'))
print('   при изменённом тексте: %r'
      % P.detect_cache_stem('ТГК-14_6мес_2025.pdf', P.DETECT_PROMPT + ' x'))
print()
print('существующие файлы кэша детекции:')
PAGES = P.PAGESDIR
for f in sorted(os.listdir(PAGES)):
    if f.startswith('_llm_') and '_detect' in f and f.endswith('.json'):
        print('   %s' % f)
print()
# сколько документов получит свой кэш обратно
import re
stems = set()
for f in os.listdir(PAGES):
    m = re.match(r'^_llm_(.+)_detect(_pv)?\.json$', f)
    if m:
        stems.add(m.group(1))
print('документов со старым кэшем детекции: %d' % len(stems))
print('из них получат кэш обратно при активном профиле %r: '
      % P.ACTIVE_PROFILE.name, end='')
inf = P._provider_infix()
ok = sum(1 for s in stems if os.path.exists(
    os.path.join(PAGES, f'_llm_{P.detect_cache_stem(s + ".pdf")}{inf}.json')))
print('%d из %d' % (ok, len(stems)))
print()
print('значит откат подсказки не требует платить заново.')
