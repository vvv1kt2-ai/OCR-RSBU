#!/usr/bin/env python3
"""Сборщик данных для индекса _ИНДЕКС.md.

Запуск:  python _index_dump.py
Результат: _index_dump.json — таблица файлов с описаниями и темами.
Индекс随后 пишется вручную (или автоматически) на основе этого JSON.
"""
import os, json, re, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

# --- helpers ---

def read_head(path, n=15):
    """Прочитать первые n строк файла."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return [f.readline() for _ in range(n)]
    except Exception:
        return []

def extract_py_doc(lines):
    """Извлечь первую строку docstring (после # coding или сразу)."""
    text = "".join(lines)
    # triple-quoted docstring after coding line or at top
    m = re.search(r'(?:(?:#.*coding.*|#!.*|\"\"\"|\'\'\')[^\n]*\n)*?\s*(?:\"\"\"(.+?)\"\"\"|\'\'\'(.+?)\'\'\')', text, re.DOTALL)
    if m:
        doc = (m.group(1) or m.group(2) or "").strip()
        return doc.split("\n")[0] if doc else ""
    # fallback: first non-import, non-comment, non-empty line
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("import ") and not s.startswith("from "):
            if s.startswith(('"""', "'''")):
                return s.strip("'\" ")
            return s[:120]
    return ""

def extract_md_heading(lines):
    """Извлечь первый заголовок # ... из markdown."""
    for line in lines:
        m = re.match(r'^#\s+(.+)', line.strip())
        if m:
            return m.group(1).strip()
    return lines[0].strip()[:120] if lines else ""

def extract_txt_desc(lines):
    """Первая непустая строка."""
    for line in lines:
        s = line.strip()
        if s:
            return s[:120]
    return ""

def human_size(b):
    if b < 1024:
        return f"{b} B"
    if b < 1024*1024:
        return f"{b/1024:.1f} KB"
    return f"{b/(1024*1024):.1f} MB"

# --- classify ---

THEME_PATTERNS = [
    # Поставщики и цены
    (r"_pv_|_polza|_provider_|_catalog|_pricing|_switch_|plusvibe|polza", "поставщики и цены"),
    # Расход токенов / reasoning
    (r"_reasoning|_cost_|_session_cost|_session_reason|_usage|_tokens", "расход токенов и reasoning"),
    # Детекция страниц
    (r"_detect_", "детекция страниц"),
    # Эскалация
    (r"_esc_|эскал", "эскалация"),
    # Арифметические правила
    (r"_rules_|_check_rules|_dup_codes|_rent_|1215|1120|1130|1140|1200|1100|2300", "правила проверки форм"),
    # Кэш / идентичность
    (r"_cache_|_identity_|_migrate_cache|dbg_cachehit", "кэш и идентичность"),
    # Дефекты 4.1 / 4.2
    (r"_fix4[12]|_contamination|_svod_contam", "дефекты 4.1 и 4.2"),
    # Свод (svod)
    (r"_svod_", "свод и его сборка"),
    # Время / поведение агента
    (r"_ВРЕМЯ|_session_timing|_workload|_status_stats|_session_final|_session_tools", "время работы и поведение агента"),
    # Корпус / объём / текстовый слой
    (r"_corpus|_textlayer|_scale_|_scope_|_trunc|_missing_total", "корпус и текстовый слой"),
]

def classify(filename):
    """Определить тему по имени файла."""
    fn = filename.lower()
    for pat, theme in THEME_PATTERNS:
        if re.search(pat, fn, re.IGNORECASE):
            return theme
    # Доп. классификация по md-файлам
    if filename.endswith(".md"):
        md_themes = {
            "d42": "дефекты 4.1 и 4.2", "d43": "дефекты 4.1 и 4.2",
            "rules": "правила проверки форм",
            "arbiter": "поставщики и цены",
            "quality": "поставщики и цены",
            "diff": "корпус и текстовый слой",
            "missing": "правила проверки форм",
            "clean": "чистка инвентаря",
            "МОДЕЛИ": "модели и рассуждения",
            "РАССУЖДЕНИЯ": "модели и рассуждения",
            "РЕШЕНИЯ": "решения и брифы",
            "ЧИСТКА": "чистка инвентаря",
            "ЭСКАЛАЦИЯ": "эскалация",
        }
        for key, theme in md_themes.items():
            if key.lower() in fn:
                return theme
    return "прочее"

# --- main ---

def main():
    files = []

    # 1. Корень: все _* файлы
    for entry in sorted(os.listdir(ROOT)):
        fp = os.path.join(ROOT, entry)
        if not os.path.isfile(fp) or not entry.startswith("_"):
            continue
        stat = os.stat(fp)
        ext = os.path.splitext(entry)[1].lower()
        lines = read_head(fp)

        if ext == ".py":
            desc = extract_py_doc(lines)
        elif ext == ".md":
            desc = extract_md_heading(lines)
        elif ext == ".json":
            desc = "(JSON-данные)"
        elif ext == ".txt":
            desc = extract_txt_desc(lines)
        elif ext == ".log":
            desc = "(лог)"
        elif ext == ".csv":
            desc = "(CSV-данные)"
        else:
            desc = ""

        if not desc:
            desc = entry

        theme = classify(entry)

        # Определяем тип
        ftype = "данные"
        if ext == ".py":
            ftype = "скрипт"
        elif ext == ".md":
            ftype = "отчёт"
        elif ext == ".json":
            ftype = "JSON"
        elif ext == ".txt":
            ftype = "текст"
        elif ext == ".log":
            ftype = "лог"
        elif ext == ".csv":
            ftype = "CSV"

        # Связь md → py (если есть парный скрипт)
        generated_by = ""
        if ftype == "отчёт":
            pair_py = entry.replace(".md", ".py")
            if os.path.isfile(os.path.join(ROOT, pair_py)):
                generated_by = pair_py

        files.append({
            "name": entry,
            "size": human_size(stat.st_size),
            "size_b": stat.st_size,
            "mtime": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "type": ftype,
            "desc": desc,
            "theme": theme,
            "generated_by": generated_by,
            "subdir": "(корень)",
        })

    # 2. tests/_*
    tests_dir = os.path.join(ROOT, "tests")
    if os.path.isdir(tests_dir):
        for entry in sorted(os.listdir(tests_dir)):
            fp = os.path.join(tests_dir, entry)
            if not os.path.isfile(fp) or not entry.startswith("_"):
                continue
            stat = os.stat(fp)
            lines = read_head(fp)
            desc = extract_txt_desc(lines) or entry
            files.append({
                "name": entry,
                "size": human_size(stat.st_size),
                "size_b": stat.st_size,
                "mtime": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "type": "текст",
                "desc": desc,
                "theme": "тесты",
                "generated_by": "",
                "subdir": "tests/",
            })

    # Статистика
    themes = {}
    for f in files:
        t = f["theme"]
        themes[t] = themes.get(t, 0) + 1

    md_files = [f for f in files if f["type"] == "отчёт"]
    py_files = [f for f in files if f["type"] == "скрипт"]

    report = {
        "total": len(files),
        "themes": dict(sorted(themes.items(), key=lambda x: -x[1])),
        "md_count": len(md_files),
        "py_count": len(py_files),
        "files": files,
    }

    out = os.path.join(ROOT, "_index_dump.json")
    with open(out, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    # Краткая сводка
    print(f"Всего файлов _: {len(files)}")
    print(f"Скриптов (.py): {len(py_files)}  |  Отчётов (.md): {len(md_files)}")
    print("По темам:")
    for t, n in report["themes"].items():
        print(f"  {t}: {n}")
    print(f"\nJSON → {out}")

if __name__ == "__main__":
    main()
