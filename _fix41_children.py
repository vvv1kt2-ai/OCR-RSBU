# -*- coding: utf-8 -*-
"""Whose ИНН is in the orphan transcripts, and what do the 200-dpi own-page transcripts say
about the two child rows escalation rewrote (Моторные, Эфферон)?"""
import os, re, json, glob

EX = r'D:\models\extracted'
PAGES = r'D:\models\extracted\pages'

print('=== company INNs in the final JSONs (for x_p5 identification) ===')
for f in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(f)
    if b.startswith('_'):
        continue
    d = json.load(open(f, encoding='utf-8'))
    inn = (d.get('company') or {}).get('inn')
    if inn in ('7708754375', '5032292806'):
        print('   %-36s inn=%s' % (b, inn))

print('\n=== who else has 1520 = 4225 / 8785 / 17267 (x_p5 content) ===')
for f in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(f)
    if b.startswith('_'):
        continue
    d = json.load(open(f, encoding='utf-8'))
    for it in ((d.get('balance') or {}).get('items') or []):
        if it.get('code') == '1520' and (it.get('values') or [])[:3] == [4225, 8785, 17267]:
            print('   %-36s 1520=%s name=%s' % (b, it.get('values'), it.get('name')))

print('\n=== 200-dpi own-page transcripts for the 3 victims ===')
for doc in ('Органик парк_6мес_2025', 'ТГК-14_6мес_2025', 'ТГК-14_6мес_2026'):
    fs = sorted(glob.glob(os.path.join(PAGES, doc + '_p*_200_*')))
    print('   %-26s 200dpi transcripts: %d' % (doc, len(fs)))
    for p in fs:
        print('       %-58s %d bytes' % (os.path.basename(p).encode('unicode_escape').decode()[:58],
                                         os.path.getsize(p)))

print('\n=== what the escalated transcripts print for the rewritten child rows ===')
for doc, pat in (('Моторные технологии_6мес_2025', 'Депозит'), ('Эфферон_6мес_2025', 'Депозит')):
    print('\n--- %s' % doc)
    for p in sorted(glob.glob(os.path.join(PAGES, doc + '_p*_300_*'))):
        txt = open(p, encoding='utf-8').read()
        for line in txt.splitlines():
            if pat in line:
                print('   %-46s | %s' % (os.path.basename(p).encode('unicode_escape').decode()[:46], line.strip()))
    for p in sorted(glob.glob(os.path.join(PAGES, doc + '_p*_200_*'))):
        txt = open(p, encoding='utf-8').read()
        for line in txt.splitlines():
            if pat in line:
                print('   %-46s | %s' % (os.path.basename(p).encode('unicode_escape').decode()[:46], line.strip()))
