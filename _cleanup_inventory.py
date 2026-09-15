#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Инвентаризация рабочей папки D:\models — повторяемый скрипт.
Собрать статистику, кросс-референсы, git-статус.

Использование:
    python _cleanup_inventory.py [путь_к_папке]
    (по умолчанию — текущая директория)
"""

import os
import subprocess
import re
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def run_git(cmd, cwd):
    """Выполнить git-команду и вернуть stdout."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def human_size(size_bytes):
    """Форматировать размер."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def categorize_file(rel_path, name):
    """Определить категорию файла."""
    if rel_path.startswith('pylibs/') or rel_path.startswith('pylibs\\'):
        return 'pylibs (bundled packages)'
    if rel_path.startswith('extracted/pages/') or rel_path.startswith('extracted\\pages\\'):
        return 'OCR cache (extracted/pages)'
    if rel_path.startswith('extracted/') or rel_path.startswith('extracted\\'):
        return 'extracted data (non-cache)'
    if rel_path.startswith('tests/') or rel_path.startswith('tests\\'):
        return 'tests'
    if rel_path.startswith('tmp/') or rel_path.startswith('tmp\\'):
        return 'tmp (diagnostics)'
    if rel_path.startswith('node_modules/') or rel_path.startswith('node_modules\\'):
        return 'node_modules'
    if rel_path.startswith('_pv_pages/') or rel_path.startswith('_pv_pages\\'):
        return '_pv_pages (page images)'
    if rel_path.startswith('.scratch/') or rel_path.startswith('.scratch\\'):
        return '.scratch'
    if rel_path.startswith('информация/') or rel_path.startswith('информация\\'):
        return 'информация (saved HTML)'
    if rel_path.startswith('docs/') or rel_path.startswith('docs\\'):
        return 'docs'

    ext = Path(name).suffix.lower()
    is_diag = name.startswith('_')

    if ext == '.py':
        return 'root diagnostic scripts (_*.py)' if is_diag else 'production code (*.py)'
    if ext == '.json':
        return 'root diagnostic data (_*.json)' if is_diag else 'JSON data files'
    if ext == '.csv':
        return 'root diagnostic data (_*.csv)' if is_diag else 'CSV data files'
    if ext == '.md':
        return 'root diagnostic docs (_*.md)' if is_diag else 'documentation (*.md)'
    if ext == '.txt':
        return 'root diagnostic text (_*.txt)' if is_diag else 'text files'
    if ext == '.log':
        return 'logs'
    if ext in ('.xlsx', '.xls'):
        return 'Excel files'
    if ext in ('.yml', '.yaml', '.toml', '.cfg', '.ini', '.bat', '.ps1', '.sh', '.cmd', '.gitignore'):
        return 'config/scripts'
    if ext in ('.html', '.css', '.js', '.jsx', '.tsx', '.ts'):
        return 'web/JS'
    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.bmp'):
        return 'images'
    if ext in ('.xml', '.pyd', '.dll', '.lib', '.pyc'):
        return 'binaries/build'

    return 'other'


def find_cross_references(root, diag_scripts):
    """Найти, какие _*.py скрипты ссылаются на другие _*.py."""
    references = defaultdict(list)

    # Production files
    prod_names = []
    for name in os.listdir(root):
        fp = os.path.join(root, name)
        if os.path.isfile(fp) and name.endswith('.py') and not name.startswith('_'):
            prod_names.append(name)

    for ds_name in diag_scripts:
        ds_path = os.path.join(root, ds_name)
        try:
            with open(ds_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            continue

        base = ds_name.replace('.py', '')

        # Check references from production code
        for pn in prod_names:
            if base in pn:
                continue
            try:
                pp = os.path.join(root, pn)
                with open(pp, 'r', encoding='utf-8', errors='replace') as f:
                    pc = f.read()
                if base in pc:
                    references[ds_name].append(pn)
            except Exception:
                pass

        # Check references from other _*.py
        for ds2_name in diag_scripts:
            if ds_name == ds2_name:
                continue
            base2 = ds2_name.replace('.py', '')
            if base2 in content:
                references[ds_name].append(f"→{ds2_name}")

    return references


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    root = root.resolve()
    print(f"Инвентаризация: {root}")
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. Собрать все файлы
    all_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden dirs except .scratch
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir.startswith('.') and rel_dir != '.scratch':
            continue
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, root)
            try:
                size = os.path.getsize(fp)
            except OSError:
                size = 0
            all_files.append((rel, fn, size))

    # 2. Категоризация
    categories = defaultdict(lambda: {'count': 0, 'size': 0})
    for rel, name, size in all_files:
        cat = categorize_file(rel, name)
        categories[cat]['count'] += 1
        categories[cat]['size'] += size

    print("\n### КАТЕГОРИИ ###\n")
    print(f"{'Категория':<45} {'Файлов':>8} {'Размер':>10}")
    print("-" * 65)
    sorted_cats = sorted(categories.items(), key=lambda x: -x[1]['size'])
    total_count = 0
    total_size = 0
    for cat, info in sorted_cats:
        print(f"{cat:<45} {info['count']:>8} {human_size(info['size']):>10}")
        total_count += info['count']
        total_size += info['size']
    print("-" * 65)
    print(f"{'ИТОГО':<45} {total_count:>8} {human_size(total_size):>10}")

    # 3. Диагностические скрипты в корне
    diag_py = [f for f in os.listdir(root) if f.startswith('_') and f.endswith('.py') and os.path.isfile(os.path.join(root, f))]
    diag_json = [f for f in os.listdir(root) if f.startswith('_') and f.endswith('.json') and os.path.isfile(os.path.join(root, f))]
    diag_md = [f for f in os.listdir(root) if f.startswith('_') and f.endswith('.md') and os.path.isfile(os.path.join(root, f))]
    diag_txt = [f for f in os.listdir(root) if f.startswith('_') and f.endswith('.txt') and os.path.isfile(os.path.join(root, f))]
    diag_csv = [f for f in os.listdir(root) if f.startswith('_') and f.endswith('.csv') and os.path.isfile(os.path.join(root, f))]

    print(f"\n### КОРНЕВЫЕ ДИАГНОСТИЧЕСКИЕ ФАЙЛЫ ###\n")
    for label, files in [('_*.py', diag_py), ('_*.json', diag_json), ('_*.md', diag_md), ('_*.txt', diag_txt), ('_*.csv', diag_csv)]:
        total_kb = sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.exists(os.path.join(root, f))) / 1024
        print(f"  {label}: {len(files)} файлов, {total_kb:.1f} КБ")

    # 4. Кросс-референсы
    print(f"\n### КРОСС-РЕФЕРЕНСЫ ###\n")
    refs = find_cross_references(root, diag_py)

    referenced_by_prod = {k: v for k, v in refs.items() if any(not x.startswith('→') for x in v)}
    inter_diag = {k: v for k, v in refs.items() if all(x.startswith('→') for x in v)}
    orphaned = [ds for ds in diag_py if ds not in refs]

    print(f"Ссылки из production: {len(referenced_by_prod)}")
    for k, v in referenced_by_prod.items():
        prod_refs = [x for x in v if not x.startswith('→')]
        print(f"  {k} ← {', '.join(prod_refs)}")

    print(f"\nМежскриптовые зависимости: {len(inter_diag)}")
    print(f"Орфанные (никто не ссылается): {len(orphaned)}")

    # 5. Крупные файлы
    print(f"\n### КРУПНЫЕ ФАЙЛЫ (>100 КБ) ###\n")
    large_files = [(r, n, s) for r, n, s in all_files if s > 100 * 1024]
    large_files.sort(key=lambda x: -x[2])
    for rel, name, size in large_files[:20]:
        print(f"  {human_size(size):>10}  {rel}")

    # 6. Git статус
    print(f"\n### GIT СТАТУС ###\n")
    git_files = run_git(['git', 'ls-files', '--cached'], cwd=root)
    tracked_set = set()
    for line in git_files.split('\n'):
        line = line.strip()
        if line:
            tracked_set.add(os.path.basename(line))

    tracked_diag = [f for f in diag_py + diag_json + diag_md + diag_txt + diag_csv if f in tracked_set]
    untracked_diag = [f for f in diag_py + diag_json + diag_md + diag_txt + diag_csv if f not in tracked_set]

    tracked_size = sum(os.path.getsize(os.path.join(root, f)) for f in tracked_diag if os.path.exists(os.path.join(root, f)))
    untracked_size = sum(os.path.getsize(os.path.join(root, f)) for f in untracked_diag if os.path.exists(os.path.join(root, f)))

    print(f"Отслеживаемые _*.*: {len(tracked_diag)} файлов, {human_size(tracked_size)}")
    print(f"Неотслеживаемые _*.*: {len(untracked_diag)} файлов, {human_size(untracked_size)}")

    if untracked_diag:
        print("\nНеотслеживаемые:")
        for f in untracked_diag:
            fp = os.path.join(root, f)
            sz = os.path.getsize(fp) if os.path.exists(fp) else 0
            print(f"  {f} ({human_size(sz)})")

    print("\n" + "=" * 60)
    print("Инвентаризация завершена. Файл отчёта: _ЧИСТКА_ИНВЕНТАРЬ.md")


if __name__ == '__main__':
    main()
