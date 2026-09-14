# -*- coding: utf-8 -*-
"""Defect 4.1 audit: every trace of escalation writing values into the final JSONs.

Read-only. Produces:
  _fix41_audit.json  - machine-readable findings
  _fix41_audit.md    - human-readable report
"""
import os, json, glob, re, io

EX = r'D:\models\extracted'
FORMS = ('balance', 'income_statement', 'cash_flow')

import sys
sys.path.insert(0, r'D:\models')
import pipeline as P   # for run_checks / val_map


def load(p):
    return json.load(open(p, encoding='utf-8'))


def walk(items):
    """yield (parent_index, item, is_child)"""
    for it in items or []:
        yield it, False
        for ch in (it.get('children') or []):
            yield ch, True


report = {'docs': [], 'totals': {}}

for f in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(f)
    if b.startswith('_'):
        continue
    d = load(f)
    doc = {'file': b, 'status': d.get('status'), 'forms': [], 'warnings_esc': []}
    for form in FORMS:
        res = d.get(form)
        if not res:
            continue
        rows = []
        for it, is_child in walk(res.get('items')):
            v, v1 = it.get('values'), it.get('values_ocr1')
            cb, cfb = it.get('corrected_by'), it.get('confirmed_by')
            touched = (cb is not None) or (v1 is not None) or (cfb is not None)
            if not touched:
                continue
            rows.append({'code': it.get('code'), 'name': it.get('name'), 'child': is_child,
                         'values': v, 'values_ocr1': v1,
                         'corrected_by': cb, 'confirmed_by': cfb,
                         'reverted_would_change': v1 is not None and v != v1})
        # checks now vs checks on reverted values
        cur_ok = [c.get('ok') for c in (d.get('checks') or []) if c.get('form') == form]
        rev_items = json.loads(json.dumps(res.get('items') or []))
        for it, _ in walk(rev_items):
            if it.get('values_ocr1') is not None:
                it['values'] = it['values_ocr1']
        rev_ok = [c.get('ok') for c in P.run_checks(form, rev_items)]
        if rows or cur_ok != rev_ok:
            doc['forms'].append({
                'form': form,
                'rows_touched': rows,
                'checks_now': {'n': len(cur_ok), 'fail': sum(1 for x in cur_ok if not x)},
                'checks_after_revert': {'n': len(rev_ok), 'fail': sum(1 for x in rev_ok if not x)},
                'checks_current_list': [c for c in (d.get('checks') or []) if c.get('form') == form],
                'checks_reverted_list': [dict(form=form, **c) for c in P.run_checks(form, rev_items)],
            })
    doc['warnings_esc'] = [w for w in (d.get('warnings') or []) if 'escalat' in w.lower() or 'esc' in w.lower()]
    if doc['forms'] or doc['warnings_esc']:
        report['docs'].append(doc)

tot_rows = sum(len(fm['rows_touched']) for dc in report['docs'] for fm in dc['forms'])
tot_chg = sum(1 for dc in report['docs'] for fm in dc['forms']
              for r in fm['rows_touched'] if r['reverted_would_change'])
report['totals'] = {'docs_with_traces': len(report['docs']),
                    'rows_touched': tot_rows,
                    'rows_that_would_change': tot_chg}
json.dump(report, open(os.path.join(r'D:\models\_fix41_audit.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

L = []
L.append('# Аудит дефекта 4.1: следы эскалации, пишущей значения\n')
L.append('Документов со следами: **%d**; затронутых строк: **%d**; из них изменились бы при '
         'откате: **%d**\n' % (report['totals']['docs_with_traces'],
                               report['totals']['rows_touched'],
                               report['totals']['rows_that_would_change']))
for dc in report['docs']:
    L.append('\n## %s  (status=%s)\n' % (dc['file'], dc['status']))
    for fm in dc['forms']:
        L.append('\n### %s\n' % fm['form'])
        L.append('| код | строка | values (сейчас) | values_ocr1 (до эскалации) | corrected_by | confirmed_by |')
        L.append('|---|---|---|---|---|---|')
        for r in fm['rows_touched']:
            L.append('| %s | %s%s | `%s` | `%s` | %s | %s |' % (
                r['code'], (r['name'] or '')[:34], ' (child)' if r['child'] else '',
                r['values'], r['values_ocr1'], r['corrected_by'], r['confirmed_by']))
        L.append('\nпроверки сейчас: %d, из них провалено %d' % (
            fm['checks_now']['n'], fm['checks_now']['fail']))
        L.append('проверки после отката: %d, из них провалено %d' % (
            fm['checks_after_revert']['n'], fm['checks_after_revert']['fail']))
        L.append('\nтекущие проверки:')
        for c in fm['checks_current_list']:
            L.append('- [%s] `%s`' % ('ok ' if c.get('ok') else 'FAIL', c.get('rule')))
        L.append('\nпосле отката:')
        for c in fm['checks_reverted_list']:
            L.append('- [%s] `%s`' % ('ok ' if c.get('ok') else 'FAIL', c.get('rule')))
    if dc['warnings_esc']:
        L.append('\nпредупреждения:')
        for w in dc['warnings_esc']:
            L.append('- %s' % w)

open(r'D:\models\_fix41_audit.md', 'w', encoding='utf-8').write('\n'.join(L))
print('docs with traces:', report['totals']['docs_with_traces'])
print('rows touched    :', report['totals']['rows_touched'])
print('rows to change  :', report['totals']['rows_that_would_change'])
for dc in report['docs']:
    print(' -', dc['file'], '| forms:', [fm['form'] for fm in dc['forms']],
          '| esc-warnings:', len(dc['warnings_esc']))
