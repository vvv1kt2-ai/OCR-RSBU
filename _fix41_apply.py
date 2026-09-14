# -*- coding: utf-8 -*-
"""Defect 4.1 fix: undo the values escalation wrote into the final JSONs.

Rule: escalation must never author values. Every row it rewrote is reverted to
`values_ocr1` (the pre-escalation value) UNLESS the document's own 300 dpi
transcript proves the escalation was right — that single exception is listed in
KEEP and is annotated instead of reverted.

Usage:
    python _fix41_apply.py            # dry run: report only, writes nothing
    python _fix41_apply.py --apply    # perform backup + revert + quarantine
"""
import os, sys, json, glob, shutil, time

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
BACKUP = os.path.join(EX, '_backup_4_1')
QUAR = os.path.join(PAGES, '_quarantine_4_1')
APPLY = '--apply' in sys.argv

sys.path.insert(0, r'D:\models')
import pipeline as P

M_ESC = P.M_ESC
FORMS = ('balance', 'income_statement', 'cash_flow')

# --- documents whose balance escalation read another company's cached pages ---
CONTAMINATED = {
    'Органик парк_6мес_2025.json': 'баланс Корпсана (чужой документ)',
    'ТГК-14_6мес_2025.json': 'баланс Корпсана (чужой документ)',
    'ТГК-14_6мес_2026.json': 'баланс Корпсана (чужой документ)',
}
# --- escalation rewrote values against its own transcript (contradicts the page) ---
CONTRADICTS_TRANSCRIPT = {
    'Моторные технологии_6мес_2025.json': 'значение противоречит собственному транскрипту стр. 2',
    'Эфферон_6мес_2025.json': 'значение противоречит собственному транскрипту стр. 3',
}
# --- escalation was RIGHT: the 300 dpi transcript of the document's own page confirms it ---
KEEP = {
    'Славянск ЭКО_6мес_2025.json': 'транскрипт 300 dpi стр. 2 подтверждает значения (1100 = 92 891 924, 1240 = -/-/2 942 100)',
}

POISONED_CACHE = (
    sorted(glob.glob(os.path.join(PAGES, 'x_p*')))          # orphan transcripts, name='x'
    + [os.path.join(PAGES, '_llm_Органик парк_6мес_2025.pdf_esc_balance.json'),
       os.path.join(PAGES, '_llm_ТГК-14_6мес_2025.pdf_esc_balance.json'),
       os.path.join(PAGES, '_llm_ТГК-14_6мес_2026.pdf_esc_balance.json')]
)

STAMP = time.strftime('%Y-%m-%d %H:%M:%S')
log = {'applied': APPLY, 'stamp': STAMP, 'docs': [], 'cache_quarantined': []}


def rows_of(res):
    for it in (res.get('items') or []):
        yield it
        for ch in (it.get('children') or []):
            yield ch


def recompute(d):
    """checks + status exactly as pipeline.process does at the end"""
    d['checks'] = [c for c in d.get('checks') or []]
    per_form_ok = {}
    for c in d['checks']:
        per_form_ok.setdefault(c['form'], []).append(bool(c.get('ok')))
    if d['checks'] and all(all(v) for v in per_form_ok.values()):
        d['status'] = 'ok'
    elif d['checks']:
        d['status'] = 'needs_review'
    elif not any(d.get(k) for k in FORMS):
        d['status'] = 'no_forms'
    else:
        d['status'] = 'incomplete'


targets = {**{k: ('foreign', v) for k, v in CONTAMINATED.items()},
           **{k: ('transcript', v) for k, v in CONTRADICTS_TRANSCRIPT.items()},
           **{k: ('keep', v) for k, v in KEEP.items()}}

for fn, (kind, why) in sorted(targets.items()):
    path = os.path.join(EX, fn)
    d = json.load(open(path, encoding='utf-8'))
    entry = {'file': fn, 'kind': kind, 'reason': why, 'before_status': d.get('status'), 'rows': []}
    touched_forms = set()
    for form in FORMS:
        res = d.get(form)
        if not res:
            continue
        for rec in rows_of(res):
            v, v1 = rec.get('values'), rec.get('values_ocr1')
            if v1 is None or v1 == v:
                continue
            touched_forms.add(form)
            row = {'form': form, 'code': rec.get('code'), 'name': rec.get('name'),
                   'written': v, 'pre_escalation': v1, 'action': None}
            if kind == 'keep':
                rec['escalation_verified'] = {'model': rec.get('corrected_by') or M_ESC,
                                              'pre_escalation_values': v1, 'evidence': why,
                                              'verified_at': STAMP}
                row['action'] = 'kept (escalation verified)'
            else:
                rec['values'] = v1
                rec['escalation_reverted'] = {'model': rec.get('corrected_by') or M_ESC,
                                              'rejected_values': v,
                                              'reason': why, 'reverted_at': STAMP}
                rec.pop('values_ocr1', None)
                rec.pop('corrected_by', None)
                row['action'] = 'reverted'
            entry['rows'].append(row)
        # escalation never confirmed anything in a foreign document: drop those marks
        if kind == 'foreign':
            for rec in rows_of(res):
                if rec.pop('confirmed_by', None) is not None:
                    entry.setdefault('confirmed_marks_dropped', 0)
                    entry['confirmed_marks_dropped'] = entry.get('confirmed_marks_dropped', 0) + 1
    # recompute checks for the forms we touched
    for form in sorted(touched_forms):
        res = d.get(form)
        if not res:
            continue
        fresh = [dict(form=form, **c) for c in P.run_checks(form, res['items'])]
        d['checks'] = [c for c in d['checks'] if c.get('form') != form] + fresh
        entry.setdefault('checks', {})[form] = {'fail': sum(1 for c in fresh if not c.get('ok')),
                                                 'n': len(fresh)}
    if kind == 'foreign':
        for form in sorted(touched_forms):
            d['warnings'] = [w for w in d.get('warnings') or []
                             if not (w.startswith(form + ':') and 'escalat' in w)]
            d['warnings'].append(f'{form}: эскалация отклонена — данные другого документа '
                                 f'(дефект 4.1); значения возвращены к состоянию до эскалации')
    recompute(d)
    entry['after_status'] = d.get('status')
    log['docs'].append(entry)
    print('%-34s %-11s rows=%-2d status %s -> %s' % (
        fn, kind, len(entry['rows']), entry['before_status'], entry['after_status']))
    for r in entry['rows']:
        print('    %-17s %-5s %-34s %s -> %s' % (
            r['form'], r['code'], (r['name'] or '')[:34], r['written'], r['pre_escalation']))
    if APPLY:
        os.makedirs(BACKUP, exist_ok=True)
        shutil.copy2(path, os.path.join(BACKUP, fn))
        json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print('\n--- cache to quarantine ---')
for p in POISONED_CACHE:
    ex = os.path.exists(p)
    print('   %-4s %s' % ('yes' if ex else 'MISS', os.path.basename(p).encode('unicode_escape').decode()))
    if ex:
        log['cache_quarantined'].append(os.path.basename(p))

if APPLY:
    os.makedirs(QUAR, exist_ok=True)
    for p in POISONED_CACHE:
        if os.path.exists(p):
            shutil.move(p, os.path.join(QUAR, os.path.basename(p)))
    json.dump(log, open(os.path.join(EX, '_fix41_revert_log.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\nbackup ->', BACKUP)
    print('quarantine ->', QUAR)
    print('log ->', os.path.join(EX, '_fix41_revert_log.json'))
else:
    print('\nDRY RUN — nothing written. Re-run with --apply')
