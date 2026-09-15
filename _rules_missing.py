#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evaluate candidate checks missing from the pipeline, using saved extracted JSONs.

NO LLM calls, NO network.  Pure computation over already-extracted data.

Candidate rules (from svod.py, not in pipeline.run_checks):
  IS-1: 2300 == 2200+2310+2320-2330+2340-2350  (income_statement)
  CF-1: 4100 == 4110-4120                       (cash_flow)
  CF-2: 4200 == 4210-4220                       (cash_flow)
  CF-3: 4300 == 4310-4320                       (cash_flow)
  BAL-X: 1300+1400+1500 == 1700  — NOTE: already present in pipeline
"""
import json, os, sys
from pathlib import Path

EXTRACTED = Path('D:/models/extracted')
TOL = 2  # pipeline tolerance

# ── helpers ──────────────────────────────────────────────────────────────────

def val_map(items):
    m = {}
    for it in items:
        if it.get('code'):
            m[it['code']] = it['values']
    return m

def has(*xs):
    return any(x is not None for x in xs)

def eq(a, b):
    return a is not None and b is not None and abs(a - b) <= TOL

def eq_pm(a, e):
    """Sign-independent equality with tolerance (svod.py convention)."""
    return a is not None and e is not None and (abs(a - e) <= TOL or abs(a + e) <= TOL)

def nz(*xs):
    return sum(x for x in xs if x is not None)

def n_cols(form):
    if not form or not form.get('items'):
        return 0
    return max((len(it.get('values') or []) for it in form['items']
                if it.get('values')), default=0)

def S(form, code, c):
    """Get single value from form dict."""
    if not form or not form.get('items'):
        return None
    m = val_map(form['items'])
    vals = m.get(code)
    if vals is None or c >= len(vals):
        return None
    return vals[c]

def per_col_to_ok(per_col):
    """Pipeline semantics: ok = all(not False) and any(True)."""
    return all(v is not False for v in per_col) and any(v is True for v in per_col)

# ── candidate rule definitions ───────────────────────────────────────────────
# Each returns (per_col_list, form_key) for a given document dict.

def eval_rule_is_2300(doc):
    """IS-1: 2300 == 2200+2310+2320-2330+2340-2350"""
    form = doc.get('income_statement')
    n = n_cols(form)
    per_col = []
    for c in range(n):
        s2300 = S(form, '2300', c)
        s2200 = S(form, '2200', c)
        # guard from svod.py: has(2200, 2300)
        if not has(s2200, s2300):
            per_col.append(None); continue
        expected = ((s2200 or 0) + (S(form, '2310', c) or 0) + (S(form, '2320', c) or 0)
                    - abs(S(form, '2330', c) or 0) + (S(form, '2340', c) or 0)
                    - abs(S(form, '2350', c) or 0))
        per_col.append(eq_pm(s2300, expected))
    return per_col, 'income_statement'

def eval_rule_cf_4100(doc):
    """CF-1: 4100 == 4110-4120"""
    form = doc.get('cash_flow')
    n = n_cols(form)
    per_col = []
    for c in range(n):
        a = S(form, '4100', c)
        if not has(S(form, '4110', c), S(form, '4120', c), a):
            per_col.append(None); continue
        expected = (S(form, '4110', c) or 0) - abs(S(form, '4120', c) or 0)
        per_col.append(eq_pm(a, expected))
    return per_col, 'cash_flow'

def eval_rule_cf_4200(doc):
    """CF-2: 4200 == 4210-4220"""
    form = doc.get('cash_flow')
    n = n_cols(form)
    per_col = []
    for c in range(n):
        a = S(form, '4200', c)
        if not has(S(form, '4210', c), S(form, '4220', c), a):
            per_col.append(None); continue
        expected = (S(form, '4210', c) or 0) - abs(S(form, '4220', c) or 0)
        per_col.append(eq_pm(a, expected))
    return per_col, 'cash_flow'

def eval_rule_cf_4300(doc):
    """CF-3: 4300 == 4310-4320"""
    form = doc.get('cash_flow')
    n = n_cols(form)
    per_col = []
    for c in range(n):
        a = S(form, '4300', c)
        if not has(S(form, '4310', c), S(form, '4320', c), a):
            per_col.append(None); continue
        expected = (S(form, '4310', c) or 0) - abs(S(form, '4320', c) or 0)
        per_col.append(eq_pm(a, expected))
    return per_col, 'cash_flow'

def eval_rule_bal_1345_1700(doc):
    """BAL-X: 1300+1400+1500 == 1700  (ALREADY in pipeline — duplicating for completeness)"""
    form = doc.get('balance')
    n = n_cols(form)
    per_col = []
    for c in range(n):
        s1700 = S(form, '1700', c)
        if not has(s1700):
            per_col.append(None); continue
        expected = nz(S(form, '1300', c), S(form, '1400', c), S(form, '1500', c))
        per_col.append(eq(expected, s1700))
    return per_col, 'balance'

CANDIDATE_RULES = [
    ('IS-1', '2300 == 2200+2310+2320-2330+2340-2350', eval_rule_is_2300,
     'income_statement'),
    ('CF-1', '4100 == 4110-4120', eval_rule_cf_4100, 'cash_flow'),
    ('CF-2', '4200 == 4210-4220', eval_rule_cf_4200, 'cash_flow'),
    ('CF-3', '4300 == 4310-4320', eval_rule_cf_4300, 'cash_flow'),
    ('BAL-X', '1300+1400+1500 == 1700 (dup)', eval_rule_bal_1345_1700, 'balance'),
]

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    docs = {}
    for f in sorted(EXTRACTED.glob('*.json')):
        if f.name.startswith('_'):
            continue
        with open(f, 'r', encoding='utf-8') as fh:
            docs[f.stem] = json.load(fh)
    n_total = len(docs)

    # Prepare result rows
    rows = []  # list of dicts
    for rule_id, rule_formula, eval_fn, form_key in CANDIDATE_RULES:
        has_codes = 0       # docs with at least one non-None involved code
        n_pass = 0
        n_fail = 0
        failing_docs = []

        for doc_name, doc in sorted(docs.items()):
            per_col, _ = eval_fn(doc)
            # "has codes" = at least one column produced True or False (i.e., not all None)
            if not any(v is not None for v in per_col):
                continue  # no data for this rule
            has_codes += 1
            ok = per_col_to_ok(per_col)
            if ok:
                n_pass += 1
            else:
                n_fail += 1
                failing_docs.append(doc_name)

        rows.append({
            'rule_id': rule_id,
            'formula': rule_formula,
            'form_key': form_key,
            'has_codes': has_codes,
            'n_pass': n_pass,
            'n_fail': n_fail,
            'failing_docs': failing_docs,
        })

    # Escalation cost analysis
    # Text branch (line 1168): only balance failures -> 300 dpi escalation
    # Scan branch (lines 1048-1051): ALL forms -> 300 dpi escalation
    # So: IS/CF failures only trigger escalation for scan documents (text_layer=false)
    scan_docs = []
    text_docs = []
    for doc_name, doc in sorted(docs.items()):
        tl = doc.get('source', {}).get('text_layer', False)
        if tl:
            text_docs.append(doc_name)
        else:
            scan_docs.append(doc_name)

    ESCALATION_MAX_PAGES = 8
    COST_PER_PAGE = 0.708  # RUB, PlusVibe 300 dpi
    PILOT_SIZE = 41
    CORPUS_SIZE = 173

    report_lines = []
    report_lines.append('# Анализ «вторых» проверок — которых нет в конвейере')
    report_lines.append('')
    report_lines.append(f'Документов в пилоте: **{n_total}** '
                        f'(текстовая ветка: {len(text_docs)}, скан-ветка: {len(scan_docs)})')
    report_lines.append('')
    report_lines.append('## Эскалация (escalate_failed_form)')
    report_lines.append('')
    report_lines.append('| Ветка | Форма | Эскалация? | Источник |')
    report_lines.append('|-------|-------|------------|----------|')
    report_lines.append('| Текст | balance | **ДА** | line 1168: `if key == "balance"` |')
    report_lines.append('| Текст | income_statement | нет | line 1168: только balance |')
    report_lines.append('| Текст | cash_flow | нет | line 1168: только balance |')
    report_lines.append('| Скан | balance | **ДА** | lines 1048-1051: все формы |')
    report_lines.append('| Скан | income_statement | **ДА** | lines 1048-1051: все формы |')
    report_lines.append('| Скан | cash_flow | **ДА** | lines 1048-1051: все формы |')
    report_lines.append('')
    report_lines.append('> **Вывод**: в текстовой ветке провал IS/CF = только пометка в своде, '
                        'без денег. В скан-ветке — полная эскалация (до 8 стр. × 0.708 ₽).')
    report_lines.append('')

    # Main table
    report_lines.append('## Результаты по правилам')
    report_lines.append('')
    report_lines.append('| # | Правило | Форма | Док-ов с кодами | OK | FAIL | '
                        'Лишних эск. (пилот) | ₽ пилот | ₽ корпус |')
    report_lines.append('|---|---------|-------|----------------:|----:|-----:|'
                        '-------------------:|-------:|---------:|')

    total_new_esc = 0
    total_rub_pilot = 0

    for row in rows:
        # Escalation count depends on form_key
        if row['form_key'] == 'balance':
            # Balance failures escalate in BOTH branches
            esc_pilot = row['n_fail']  # all docs are in the pilot
        else:
            # IS/CF: only scan-branch docs trigger escalation
            esc_pilot = sum(1 for d in row['failing_docs'] if d in set(scan_docs))

        esc_pages = esc_pilot * ESCALATION_MAX_PAGES
        rub_pilot = esc_pilot * ESCALATION_MAX_PAGES * COST_PER_PAGE
        rub_corpus = rub_pilot * (CORPUS_SIZE / PILOT_SIZE)
        total_new_esc += esc_pilot
        total_rub_pilot += rub_pilot

        report_lines.append(
            f'| {row["rule_id"]} | `{row["formula"]}` | {row["form_key"]} '
            f'| {row["has_codes"]} | {row["n_pass"]} | {row["n_fail"]} '
            f'| {esc_pilot} | {rub_pilot:.2f} | {rub_corpus:.2f} |')

    total_rub_corpus = total_rub_pilot * (CORPUS_SIZE / PILOT_SIZE)
    report_lines.append('')
    report_lines.append(f'**Итого лишних эскалаций (пилот):** {total_new_esc}')
    report_lines.append(f'**Итого ₽ (пилот):** {total_rub_pilot:.2f}')
    report_lines.append(f'**Итого ₽ (корпус {CORPUS_SIZE} док.):** {total_rub_corpus:.2f}')
    report_lines.append('')

    # Detailed failing docs per rule
    report_lines.append('## Новые проваливающие документы')
    report_lines.append('')
    for row in rows:
        report_lines.append(f'### {row["rule_id"]}: `{row["formula"]}` ({row["form_key"]})')
        if not row['failing_docs']:
            report_lines.append('Нет провалов.')
        else:
            for d in row['failing_docs']:
                tl = 'скан' if d in set(scan_docs) else 'текст'
                report_lines.append(f'- {d} ({tl})')
        report_lines.append('')

    # Conclusions
    report_lines.append('## Выводы')
    report_lines.append('')
    report_lines.append('1. **IS-1 (2300)** — проверка есть в своде, но нет в конвейере. '
                        'Провалы в текстовой ветке = бесплатные пометки; в скан-ветке = эскалация.')
    report_lines.append('2. **CF-1/CF-2/CF-3 (4100/4200/4300)** — аналогично. '
                        'Для документов с текстовым слоем провал = 0 ₽ (только пометка). '
                        'Для сканов — эскалация.')
    report_lines.append('3. **BAL-X (1300+1400+1500 == 1700)** — УЖЕ ЕСТЬ в pipeline.py '
                        '(строка 393). Дублировать бессмысленно; «новых» провалов не будет.')
    report_lines.append('')

    # Note about BAL-X
    report_lines.append('### Важное замечание по BAL-X')
    report_lines.append('')
    report_lines.append('Правило `1300+1400+1500 == 1700` реализовано в `pipeline.py` '
                        '(строка 393) и в `svod.py` `check_balance` (строка 122). '
                        'Оно **не является «отсутствующим»** — конвейер его уже проверяет. '
                        'Результаты ниже приведены для полноты, но они совпадают '
                        'с уже сохранёнными checks.')
    report_lines.append('')

    report = '\n'.join(report_lines)

    # Write report
    report_path = Path('D:/models/_rules_missing.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'Отчёт записан: {report_path}')

    # Print summary to stdout
    print()
    print('=== КРАТКАЯ СВОДКА ===')
    for row in rows:
        if row['form_key'] == 'balance':
            esc = row['n_fail']
        else:
            esc = sum(1 for d in row['failing_docs'] if d in set(scan_docs))
        print(f"{row['rule_id']:6s} | кодов={row['has_codes']:2d} | "
              f"ok={row['n_pass']:2d} fail={row['n_fail']:2d} | "
              f"эск.={esc} | формула: {row['formula']}")
    print()
    print(f'Итого новых эскалаций на пилоте (41): {total_new_esc}')
    print(f'Итого ₽ на пилоте: {total_rub_pilot:.2f}')
    print(f'Итого ₽ на корпусе (173): {total_rub_corpus:.2f}')
    print()
    print('Эскалация формы:')
    print('  Текстовая ветка (line 1168): только balance → эскалация')
    print('  Текстовая ветка: IS/CF → только пометка, 0 ₽')
    print('  Скан-ветка (lines 1048-1051): все формы → эскалация')


if __name__ == '__main__':
    main()
