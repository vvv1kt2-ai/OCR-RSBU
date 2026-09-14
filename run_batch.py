# -*- coding: utf-8 -*-
r"""Batch runner: process the 39 selected files, skipping already-extracted ones."""
import subprocess, sys, os, json, time

OUTDIR = r'D:\models\extracted'
NAMES = ['ТГК-14', 'КИФА', 'Проект 111', 'Афанасий', 'Омега', 'Байсэл',
         'Бианка премиум', 'Сибсульфур', 'Простая еда', 'Славянск ЭКО',
         'НовосибирскАвтодор', 'Моторные технологии', 'Эфферон',
         'Нижегородец Восток', 'Финэква', 'Органик парк', 'ИПС',
         'Артген (ИСКЧ)', 'Смартфакт', 'КЛВЗ Кристалл']

targets = []
for n in NAMES:
    for y in (2025, 2026):
        p = rf'D:\data-scraping\downloads\{n}_6мес_{y}.pdf'
        if os.path.exists(p): targets.append(p)
missing = [f'{n}_6мес_{y}' for n in NAMES for y in (2025, 2026)
           if not os.path.exists(rf'D:\data-scraping\downloads\{n}_6мес_{y}.pdf')]
print(f'targets: {len(targets)}, missing: {missing}')

todo = []
for p in targets:
    out = os.path.join(OUTDIR, os.path.splitext(os.path.basename(p))[0] + '.json')
    if not os.path.exists(out):
        todo.append(p)
print(f'todo: {len(todo)} (already done: {len(targets) - len(todo)})')

failed = []
for i, p in enumerate(todo):
    print(f'--- [{i+1}/{len(todo)}] {os.path.basename(p)}', flush=True)
    r = subprocess.run([sys.executable, '-X', 'utf8', r'D:\models\pipeline.py', p], timeout=3600)
    if r.returncode != 0:
        failed.append(os.path.basename(p))
print('DONE')
