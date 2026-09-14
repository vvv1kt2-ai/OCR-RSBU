# -*- coding: utf-8 -*-
"""Page-cache inventory: only .md files, two known shapes, plus anything unrecognised."""
import os, re, collections

PAGES = r'D:\models\extracted\pages'
sh1 = re.compile(r'^(?P<doc>.+?)_p(?P<p>\d+)_(?P<dpi>\d+)_(?P<model>.*)\.md$')     # page transcript
sh2 = re.compile(r'^(?P<doc>.+?)_(?P<form>[a-z_]+)_p(?P<page>\d+)\.md$')          # form transcript

kind = collections.Counter()
tags = collections.Counter()
other = []
for n in sorted(os.listdir(PAGES)):
    if not os.path.isfile(os.path.join(PAGES, n)) or not n.endswith('.md'):
        continue
    if sh1.match(n):
        kind['page'] += 1
        tags[sh1.match(n).group('model')] += 1
    elif sh2.match(n):
        kind['form'] += 1
    else:
        kind['other'] += 1
        other.append(n)

print('kinds:', dict(kind))
print('model tags in page transcripts:', {k or '(EMPTY)': v for k, v in tags.items()})
print('\nunrecognised (%d):' % len(other))
for n in other:
    print('   ', n.encode('unicode_escape').decode())
