# -*- coding: utf-8 -*-
r"""Сопоставление пилота с корпусом: сколько страниц было у документов пилота.

Проекция «пилот → корпус» умножает цену пилота на масштаб. Если документы пилота
в среднем короче корпусных, то масштаб по числу документов занижает цену.
Проверяю по `source.pages_total` в сохранённых артефактах.
"""
import io, os, json, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

tot_pages = 0
n = 0
rows = []
esc_pages = 0
for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    src = doc.get('source') or {}
    pt = src.get('pages_total') or 0
    used = sorted(set(src.get('pages_used') or []))
    n += 1
    tot_pages += pt
    rows.append((os.path.splitext(rf)[0], pt, len(used)))

for f in os.listdir(PAGES):
    if '_esc_' in f:
        esc_pages += 1

print('пилот: документов %d, страниц всего %d, средняя длина %.1f' % (n, tot_pages, tot_pages / max(n, 1)))
print('корпус: документов 173, страниц всего 5884, средняя длина 34.0')
print()
print('страниц, отнесённых к формам (pages_used): %d, в среднем %.1f на документ'
      % (sum(r[2] for r in rows), sum(r[2] for r in rows) / max(n, 1)))
print('файлов кэша эскалации (страниц 300 dpi): %d' % esc_pages)
print()
print('длина документов пилота:')
buckets = [(1, 10), (11, 20), (21, 40), (41, 80), (81, 10 ** 6)]
for lo, hi in buckets:
    k = [r for r in rows if lo <= r[1] <= hi]
    if k:
        print('  %3d-%-4s док. %3d, страниц %5d (сред. %.0f)'
              % (lo, '∞' if hi > 10 ** 5 else hi, len(k), sum(r[1] for r in k),
                 sum(r[1] for r in k) / len(k)))
print()
ratio_doc = 173.0 / max(n, 1)
ratio_pages = 5884.0 / max(tot_pages, 1)
print('масштаб по числу документов: %.2f' % ratio_doc)
print('масштаб по числу страниц:    %.2f' % ratio_pages)
print('во сколько раз корпусный документ длиннее пилотного: %.2f'
      % ((5884.0 / 173) / (tot_pages / max(n, 1))))
