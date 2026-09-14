# -*- coding: utf-8 -*-
"""Fact-finding: duplicate codes in extracted RSBU JSONs.
Run: python _dup_codes.py
Output: stdout report.
"""
import json, re, os, glob, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from collections import defaultdict
from pathlib import Path

EXTRACTED = Path(r'D:\models\extracted')

# ──────────────────── helpers ────────────────────
def walk_items(items):
    """Yield (item, path) where path = list of parent codes (empty for top-level)."""
    for it in (items or []):
        yield it, []
        for ch in it.get('children') or []:
            yield ch, [it.get('code') or '']


def collect_codes(form):
    """Return dict: code -> list of (name, values, location, parent_chain).
    location = 'top' or 'child'."""
    result = defaultdict(list)
    items = form.get('items') or []
    for it, _ in walk_items(items):
        # We need parent chain - re-walk
        pass
    # Better: walk with full chain
    def _walk(items, chain):
        for it in (items or []):
            code = it.get('code')
            loc = 'top' if not chain else 'child'
            name = it.get('name', '')
            values = it.get('values', [])
            result[code].append({
                'name': name,
                'values': values,
                'location': loc,
                'chain': list(chain),
            })
            _walk(it.get('children') or [], chain + [code])
    _walk(items, [])
    return result


# Regex for rent-related names
RENT_RE = re.compile(r'аренд|лизинг', re.I)
AVANS_RE = re.compile(r'аванс', re.I)

FORM_NAMES = {
    'balance': '0710001 баланс',
    'income_statement': '0710002 ОФР',
    'cash_flow': '0710005 ОДДС',
}


# ──────────────────── scan all final JSONs ────────────────────
final_jsons = sorted(
    p for p in EXTRACTED.glob('*_6мес_*.json')
    if 'pages' not in str(p)
)

print(f'=== SCAN: {len(final_jsons)} final JSON files in {EXTRACTED} ===')
print()

# (a) identical-name duplicates, (b) different-name duplicates,
# (c) code at top level AND in children
dup_identical = []
dup_different = []
dup_top_and_child = []

# All items by code across all documents for cross-doc analysis
all_code_names = defaultdict(lambda: defaultdict(set))  # code -> doc -> set(names)

for jpath in final_jsons:
    fname = jpath.name
    doc = json.load(open(jpath, encoding='utf-8'))
    for form_key in ('balance', 'income_statement', 'cash_flow'):
        form = doc.get(form_key)
        if not form:
            continue
        codes = collect_codes(form)
        # Items that have a code (skip code=None)
        for code, entries in codes.items():
            if code is None:
                continue
            # Track names across documents
            for e in entries:
                all_code_names[code][fname].add(e['name'])

            if len(entries) < 2:
                continue

            # Check (a) vs (b)
            names = [e['name'] for e in entries]
            values = [e['values'] for e in entries]
            locations = [e['location'] for e in entries]
            chains = [e['chain'] for e in entries]

            if len(set(names)) == 1:
                dup_identical.append({
                    'file': fname, 'form': FORM_NAMES.get(form_key, form_key),
                    'code': code, 'name': names[0],
                    'count': len(entries), 'values': values,
                    'locations': locations, 'chains': chains,
                })
            else:
                dup_different.append({
                    'file': fname, 'form': FORM_NAMES.get(form_key, form_key),
                    'code': code,
                    'entries': entries,
                })

            # Check (c): code appears at top level AND inside children
            locs = set(locations)
            if 'top' in locs and 'child' in locs:
                dup_top_and_child.append({
                    'file': fname, 'form': FORM_NAMES.get(form_key, form_key),
                    'code': code,
                    'entries': entries,
                })


# ──────────────────── 1. DUPLICATE REPORT ────────────────────
print('=' * 80)
print('SECTION 1: DUPLICATE CODES WITHIN A SINGLE FORM OF A SINGLE DOCUMENT')
print('=' * 80)
print()
print(f'Case (a) — duplicate code, IDENTICAL name: {len(dup_identical)} occurrences')
print(f'Case (b) — duplicate code, DIFFERENT names: {len(dup_different)} occurrences')
print(f'Case (c) — code at top level AND inside children: {len(dup_top_and_child)} occurrences')
print()

print('-' * 80)
print('CASE (b) — DUPLICATE CODE WITH DIFFERENT NAMES (all instances)')
print('-' * 80)
for d in dup_different:
    print(f"\n  File: {d['file']}")
    print(f"  Form: {d['form']}")
    print(f"  Code: {d['code']}")
    for i, e in enumerate(d['entries']):
        loc = e['location']
        chain = ' > '.join(c for c in e['chain'] if c) or '(top-level)'
        vals = e['values']
        print(f"    [{i+1}] name: \"{e['name']}\"")
        print(f"        location: {loc}  chain: {chain}")
        print(f"        values: {vals}")
    print()

if not dup_different:
    print('  (none found)')
print()

print('-' * 80)
print('CASE (c) — CODE AT TOP LEVEL AND INSIDE CHILDREN (all instances)')
print('-' * 80)
for d in dup_top_and_child:
    print(f"\n  File: {d['file']}")
    print(f"  Form: {d['form']}")
    print(f"  Code: {d['code']}")
    for i, e in enumerate(d['entries']):
        loc = e['location']
        chain = ' > '.join(c for c in e['chain'] if c) or '(top-level)'
        print(f"    [{i+1}] name: \"{e['name']}\"")
        print(f"        location: {loc}  chain: {chain}")
        print(f"        values: {e['values']}")
    print()

if not dup_top_and_child:
    print('  (none found)')
print()

print('-' * 80)
print('CASE (a) — DUPLICATE CODE WITH IDENTICAL NAME (summary)')
print('-' * 80)
for d in dup_identical:
    print(f"  {d['file']} | {d['form']} | code {d['code']} | name=\"{d['name']}\" | x{d['count']}")
    for i, vals in enumerate(d['values']):
        print(f"    [{i+1}] location={d['locations'][i]} chain={' > '.join(c for c in d['chains'][i] if c) or '(top)'} values={vals}")
print()

# ──────────────────── 5. CROSS-DOC CODE AMBIGUITY ────────────────────
print('=' * 80)
print('SECTION 5: CODES CARRYING DIFFERENT NAMES ACROSS DOCUMENTS')
print('=' * 80)
print()
cross_ambig = {}
for code in sorted(all_code_names.keys()):
    names_by_doc = all_code_names[code]
    all_names = set()
    for doc_names in names_by_doc.values():
        all_names.update(doc_names)
    # Filter out None/empty
    all_names = {n for n in all_names if n}
    if len(all_names) > 1:
        cross_ambig[code] = names_by_doc

if cross_ambig:
    for code in sorted(cross_ambig.keys()):
        names_by_doc = cross_ambig[code]
        print(f"  Code {code}:")
        all_names_for_code = set()
        for doc, names in sorted(names_by_doc.items()):
            for n in names:
                all_names_for_code.add(n)
        for n in sorted(all_names_for_code):
            docs_with = [doc for doc, names in names_by_doc.items() if n in names]
            print(f"    \"{n}\"  ←  {', '.join(docs_with)}")
        print()
else:
    print('  (no cross-document ambiguity found)')
print()

# ──────────────────── 4. RENT ROWS ────────────────────
print('=' * 80)
print('SECTION 4: RENT / LEASE ROWS')
print('=' * 80)
print()

for jpath in final_jsons:
    fname = jpath.name
    doc = json.load(open(jpath, encoding='utf-8'))
    form = doc.get('balance')
    if not form:
        continue
    rent_items = []
    for it, chain in walk_items(form.get('items') or []):
        name = it.get('name', '')
        code = it.get('code', '')
        if AVANS_RE.search(name):
            continue
        if not RENT_RE.search(name):
            continue
        in_1450_1550 = '1450' in chain or '1550' in chain
        loc = 'top-level' if not chain else f"child of {' > '.join(c for c in chain if c)}"
        rent_items.append({
            'code': code, 'name': name, 'values': it.get('values'),
            'location': loc, 'in_1450_1550': in_1450_1550, 'chain': chain,
        })
    if rent_items:
        print(f"  {fname}:")
        for ri in rent_items:
            inside = 'INSIDE 1450/1550' if ri['in_1450_1550'] else 'OUTSIDE 1450/1550'
            print(f"    code={ri['code']} name=\"{ri['name']}\" values={ri['values']}")
            print(f"      location: {ri['location']}  → {inside}")
        print()

print()

# ──────────────────── 2 & 3. CODE ANALYSIS FROM pipeline.py / svod.py ────────────────────
print('=' * 80)
print('SECTION 2: HOW pipeline.py HANDLES DUPLICATES')
print('=' * 80)
print()
print('File: D:\\models\\pipeline.py')
print()
print('A) val_map (lines 291-295):')
print('   def val_map(items):')
print('       m = {}')
print('       for it in items:')
print('           if it.get(\"code\"): m[it[\"code\"]] = it[\"values\"]')
print('       return m')
print()
print('   This iterates items in order. For a given code, LAST assignment wins')
print('   because dict overwrites previous values for the same key.')
print('   val_map operates on top-level items only (does NOT descend into children).')
print()
print('B) _normalize_llm (lines 439-456):')
print('   def _normalize_llm(llm, form_key=None):')
print('       raw = llm.get(\"items\", [])')
print('       if form_key == \"balance\": _assign_bal_codes(raw)')
print('       items, seen = [], set()')
print('       for it in raw:')
print('           code = it.get(\"code\")')
print('           rec = {\"code\": code, ...}')
print('           if code and code in KNOWN_TOP and code not in seen:')
print('               seen.add(code); items.append(rec)   # FIRST match kept as top-level')
print('           elif items:')
print('               items[-1].setdefault(\"children\", []).append(rec)  # duplicate becomes child')
print('           else:')
print('               items.append(rec)')
print('       return items')
print()
print('   Behavior:')
print('   - If code is in KNOWN_TOP and NOT yet seen → kept as top-level item')
print('   - If code is in KNOWN_TOP but ALREADY seen → demoted to child of last top-level item')
print('   - If code is NOT in KNOWN_TOP → also demoted to child')
print()
print('   Information loss: the duplicate (second occurrence) becomes a child of whatever the')
print('   last top-level item was. Its original name is preserved in the child, but in')
print('   svod.get_val() only the LAST top-level item\'s values are read, so the second')
print('   top-level item\'s values are lost if it was demoted. If the first was demoted,')
print('   its values are also lost from top-level.')
print()

print('=' * 80)
print('SECTION 3: HOW svod.py PICKS A VALUE WHEN CODE IS DUPLICATED')
print('=' * 80)
print()
print('File: D:\\models\\svod.py, lines 69-77:')
print('   def get_val(form, code, idx):')
print('       \"\"\"Значение кода в колонке idx; из ПОСЛЕДНЕГО верхнеуровневого item с кодом.\"\"\"')
print('       if form is None or idx is None:')
print('           return None')
print('       items = [it for it in (form.get(\"items\") or []) if it.get(\"code\") == code]')
print('       if not items:')
print('           return None')
print('       v = items[-1].get(\"values\") or []')
print('       return v[idx] if idx < len(v) else None')
print()
print('   The docstring says "ПОСЛЕДНЕГО" (LAST). It filters top-level items for code match,')
print('   then takes items[-1]. If _normalize_llm already deduplicated (demoted second to child),')
print('   this returns the first/only occurrence. If the raw JSON still has duplicates at top')
print('   level (text branch, not _normalize_llm), it picks the LAST one by document order.')
print()
print('File: D:\\models\\svod_build.py, lines 85-87, 91-92:')
print('   bal_idx = svod.col_index_balance(bal, year)')
print('   ...')
print('   for code in svod.BAL_CODES:')
print('       v = svod.get_val(bal, code, bal_idx)')
print()
print('   svod_build.py calls svod.get_val, so the same LAST-top-level-item rule applies.')
print()
print('File: D:\\models\\svod_build.py, lines 96-105 (rent addition):')
print('   long_v, short_v, notes, susp = svod.rent_extract(bal, bal_idx)')
print('   base1450 = svod.get_val(bal, \"1450\", bal_idx)')
print('   base1550 = svod.get_val(bal, \"1550\", bal_idx)')
print('   if long_v is not None:')
print('       cells[(yk, \"1450\")] = (base1450 or 0) + long_v')
print('   elif base1450 is not None:')
print('       cells[(yk, \"1450\")] = base1450')
print('   if short_v is not None:')
print('       cells[(yk, \"1550\")] = (base1550 or 0) + short_v')
print('   elif base1550 is not None:')
print('       cells[(yk, \"1550\")] = base1550')
print()
print('   So: base value for 1450/1550 = get_val (LAST top-level item with that code),')
print('   then rent_extract adds long/short rent to it IF rent rows sit OUTSIDE 1450/1550.')
print()

print('=' * 80)
print('SECTION 4 continued: svod.py rent_extract logic')
print('=' * 80)
print()
print('File: D:\\models\\svod.py, lines 224-289:')
print('   rent_extract() walks ALL items (top + children). For each rent-related item:')
print('   - Skips if name matches AVANS_RE (advance payments)')
print('   - Skips if code is 1450 or 1550 themselves (the container)')
print('   - Matches LONG_RENT_RE, SHORT_RENT_RE, or LEASE_RE against name')
print('   - CRITICAL: if \"1450\" in chain or \"1550\" in chain → SKIPPED (already inside)')
print('     with note "внутри кода, не плюсовалась"')
print('   - Otherwise: added to long_sum or short_sum based on name/parent regex')
print('   - If parent unknown: suspicion=True, added to short_sum anyway')
print()
print('   This implements the user rule: rent is added to 1450/1550 ONLY when OUTSIDE the code.')
print()
