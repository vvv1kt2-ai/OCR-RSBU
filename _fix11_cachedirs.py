# -*- coding: utf-8 -*-
r"""Где лежат кэши какого поставщика — это определяет цену перехода на plusvibe.

Ключ страницы включает суффикс поставщика ('' у polza, '_pv' у plusvibe), поэтому
транскрипты одного поставщика другому не подходят. Считаю по всем каталогам кэшей.
"""
import os, re, sys, collections

sys.path.insert(0, r'D:\models')
import pipeline as P

print('_provider_infix() сейчас: %r' % P._provider_infix())
print('cache_suffix профиля %r: %r' % (P.ACTIVE_PROFILE.name,
                                       P.ACTIVE_PROFILE.cache_suffix))
print()

ROOT = r'D:\models'
dirs = []
for name in sorted(os.listdir(ROOT)):
    full = os.path.join(ROOT, name)
    if os.path.isdir(full) and ('page' in name.lower() or 'cache' in name.lower()):
        dirs.append(full)
full = os.path.join(ROOT, 'extracted', 'pages')
if os.path.isdir(full) and full not in dirs:
    dirs.append(full)

for d in dirs:
    files = os.listdir(d)
    pv = [f for f in files if f.endswith('_pv.json') or '_pv_' in f or re.search(r'_pv\.md$', f)]
    nopv = [f for f in files if f not in pv]
    md = [f for f in files if f.endswith('.md')]
    md_pv = [f for f in md if re.search(r'_pv[_.]', f)]
    print('%s' % d)
    print('   всего файлов: %d  (транскриптов .md: %d)' % (len(files), len(md)))
    print('   с признаком _pv: %d   без: %d' % (len(pv), len(nopv)))
    print('   транскриптов _pv: %d из %d' % (len(md_pv), len(md)))
    print()

# образец имени транскрипта из каждого каталога
print('образцы имён транскриптов (по 2 на каталог):')
for d in dirs:
    md = [f for f in os.listdir(d) if f.endswith('.md')][:2]
    for f in md:
        print('   %s' % f)
print()
print('если в каталоге только имена без _pv — кэш сделан polza, и прогон plusvibe')
print('его не переиспользует: ключ содержит поставщика.')
