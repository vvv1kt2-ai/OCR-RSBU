# -*- coding: utf-8 -*-
r"""Разведка корпуса: объём, текстовый слой, где пояснения и аудиторское заключение.

Отвечает на три вопроса без единого вызова LLM:
  1. каков настоящий объём (документов, страниц, документов >10 страниц);
  2. у какой доли страниц есть текстовый слой (его можно читать бесплатно);
  3. на каких страницах пояснения и аудиторское заключение (и есть ли оно вообще).

Подробности — в `_corpus_survey.csv`, на экран только сводка.
"""
import os, io, csv, re, sys

sys.path.insert(0, r'D:\models')
import pipeline  # добавляет pylibs в sys.path
import fitz

SRC = r'D:\data-scraping\downloads'
OUT = r'D:\models\_corpus_survey.csv'

AUD = re.compile(r'аудиторск\w*\s+заключени', re.I)
NOTES = re.compile(r'пояснени\w*\s+к\s+бухгалтерск', re.I)
FORMS = re.compile(r'071000[125]')

rows = []
for root, _, files in os.walk(SRC):
    for fn in sorted(files):
        if not fn.lower().endswith('.pdf'):
            continue
        path = os.path.join(root, fn)
        try:
            doc = fitz.open(path)
        except Exception as e:
            rows.append({'file': fn, 'pages': 0, 'text_pages': 0, 'chars': 0,
                         'aud': '', 'notes': '', 'err': str(e)[:60]})
            continue
        npages = doc.page_count
        text_pages = 0
        chars = 0
        aud, notes = [], []
        for i in range(npages):
            try:
                t = doc[i].get_text() or ''
            except Exception:
                t = ''
            chars += len(t)
            if len(t.strip()) > 50:
                text_pages += 1
            if AUD.search(t):
                aud.append(i + 1)
            if NOTES.search(t):
                notes.append(i + 1)
        doc.close()
        rows.append({'file': fn, 'pages': npages, 'text_pages': text_pages, 'chars': chars,
                     'aud': ','.join(map(str, aud[:6])), 'notes': ','.join(map(str, notes[:8])),
                     'err': ''})

with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

n = len(rows)
tot = sum(r['pages'] for r in rows)
tp = sum(r['text_pages'] for r in rows)
ch = sum(r['chars'] for r in rows)
big = [r for r in rows if r['pages'] > 10]
print('документов: %d, страниц: %d, символов текстового слоя: %d' % (n, tot, ch))
print('документов >10 страниц: %d (страниц в них %d)' % (len(big), sum(r['pages'] for r in big)))
print('страниц с текстовым слоем (>50 симв.): %d из %d = %.0f%%' % (tp, tot, 100.0 * tp / max(tot, 1)))
print()
print('распределение по числу страниц:')
buckets = [(1, 10), (11, 20), (21, 40), (41, 80), (81, 200), (201, 10 ** 6)]
for lo, hi in buckets:
    k = [r for r in rows if lo <= r['pages'] <= hi]
    if k:
        print('  %3d-%-4s док. %3d, страниц %5d (сред. %.0f)'
              % (lo, '∞' if hi > 10 ** 5 else hi, len(k), sum(r['pages'] for r in k),
                 sum(r['pages'] for r in k) / len(k)))
print()
aud_docs = [r for r in rows if r['aud']]
notes_docs = [r for r in rows if r['notes']]
print('аудиторское заключение найдено: %d документов из %d' % (len(aud_docs), n))
for r in aud_docs[:8]:
    print('  %-42s стр. %d, заключение на %s' % (r['file'][:42], r['pages'], r['aud']))
print('пояснения к балансу найдены: %d документов из %d' % (len(notes_docs), n))
print()
no_text = [r for r in rows if r['text_pages'] == 0 and r['pages']]
print('документов без текстового слоя совсем: %d' % len(no_text))
for r in no_text[:8]:
    print('  %-42s стр. %d' % (r['file'][:42], r['pages']))
