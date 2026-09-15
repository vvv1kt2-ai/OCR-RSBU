# -*- coding: utf-8 -*-
r"""Происхождение кэша: какой поставщик и какая модель сделали существующие транскрипты.

Ключ страницы содержит и модель, и поставщика, поэтому по имени файла видно, кто писал.
Это решает, что переиспользует целевой прогон на plusvibe.
"""
import collections, io, os, re, sys, time

PAGES = r'D:\models\extracted\pages'
MODELS = ('gemini-3.8-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-flash',
          'deepseek-v4.1-flash', 'anthropic')

files = [f for f in os.listdir(PAGES) if f.endswith('.md')]
print('транскриптов всего: %d' % len(files))
print()

by_model = collections.Counter()
by_prov = collections.Counter()
oldest = {}
newest = {}
for f in files:
    tag = None
    for m in MODELS:
        if m in f:
            tag = m
            break
    prov = 'plusvibe' if re.search(r'_pv_', f) else 'polza'
    by_model[tag] += 1
    by_prov[prov] += 1
    t = os.path.getmtime(os.path.join(PAGES, f))
    if prov not in oldest or t < oldest[prov]:
        oldest[prov] = t
    if prov not in newest or t > newest[prov]:
        newest[prov] = t

print('по поставщику:')
for k, v in by_prov.most_common():
    print('   %-10s %4d   (от %s до %s)'
          % (k, v, time.strftime('%d.%m %H:%M', time.localtime(oldest[k])),
             time.strftime('%d.%m %H:%M', time.localtime(newest[k]))))
print()
print('по модели:')
for k, v in by_model.most_common():
    print('   %-22s %4d' % (k, v))
print()

print('образцы имён с _pv (plusvibe):')
n = 0
for f in sorted(files):
    if '_pv_' in f:
        print('   %s' % f); n += 1
        if n >= 12:
            break
print()
print('образцы имён без _pv (polza):')
n = 0
for f in sorted(files):
    if '_pv_' not in f:
        print('   %s' % f); n += 1
        if n >= 4:
            break
print()
for extra in (r'D:\models\_pv_usage.json',):
    if os.path.exists(extra):
        print('%s: изменён %s' % (os.path.basename(extra),
                                  time.strftime('%d.%m.%Y %H:%M',
                                                time.localtime(os.path.getmtime(extra)))))
