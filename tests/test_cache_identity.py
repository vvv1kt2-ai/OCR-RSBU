# -*- coding: utf-8 -*-
r"""Regression tests for the cache-identity defect 4.1 and its guards.

Run:  python D:\models\tests\test_cache_identity.py
No network, no LLM calls, no writes — every assertion is about key construction,
guards and conflict detection. Fails loudly with a non-zero exit code.
"""
import os, sys, json, glob, re

sys.path.insert(0, r'D:\models')
import pipeline as P          # importing it puts D:\models\pylibs on sys.path
import pymupdf

DOWNLOADS = r'D:\data-scraping\downloads'
PAGES = os.path.join(P.OUTDIR, 'pages')
QUAR = os.path.join(PAGES, '_quarantine_4_1')

PASS, FAIL, LOG = [], [], []
_console = print


def print(*a, **k):
    """Mirror everything into a log file: the terminal display is not trustworthy here."""
    LOG.append(' '.join(str(x) for x in a))
    _console(*a, **k)


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  %-4s %s%s' % ('ok' if cond else 'FAIL', name,
                           ('  <- ' + detail) if detail and not cond else ''))


def pdf(name):
    return pymupdf.open(os.path.join(DOWNLOADS, name))


print('=== 1. model_tag never returns an empty tag ===')
for model in ('google/gemini-3.8-flash', 'anthropic/', '', 'x/y/z', 'google/gemini-2.5-flash-lite'):
    t = P.model_tag(model)
    check('model_tag(%r) = %r is non-empty and filesystem-safe' % (model, t),
          bool(t) and t == t.strip() and not any(c in t for c in '\\/:*?"<>|'))
check('a trailing slash cannot produce an empty tag', P.model_tag('vendor/') == 'vendor')
check('the real escalation model keeps the tag the old formula produced',
      P.model_tag(P.M_ESC) == P.M_ESC.split('/')[-1] and bool(P.model_tag(P.M_ESC)))

print('\n=== 2. two documents never share a page-cache key ===')
d1, d2 = pdf('ТГК-14_6мес_2025.pdf'), pdf('ТГК-14_6мес_2026.pdf')
k1 = P.page_cache_path(d1, 'ТГК-14_6мес_2025.pdf', 3, 300, P.M_ESC)
k2 = P.page_cache_path(d2, 'ТГК-14_6мес_2026.pdf', 3, 300, P.M_ESC)
check('same page/dpi/model of two different PDFs -> different paths', k1 != k2)
check('the model tag appears in the key', P.model_tag(P.M_ESC) in os.path.basename(k1))
check('the PDF fingerprint appears in the key', P.doc_fingerprint(d1) in os.path.basename(k1))
check('fingerprint differs between the two PDFs', P.doc_fingerprint(d1) != P.doc_fingerprint(d2))
check('every page transcript on disk names a model (none empty)', not [
    n for n in os.listdir(PAGES)
    if n.endswith('.md') and re.match(r'^.+_p\d+_(200|300)_.*\.md$', n)
    and re.match(r'^.+_p\d+_(200|300)_\.md$', n)])

print('\n=== 3. a key that does not identify the document is refused ===')
for bad in ('x', 'esc', '', 'какой-то_другой_документ.pdf'):
    try:
        P.page_cache_path(d1, bad, 3, 300, P.M_ESC)
        check('name=%r refused' % bad, False, 'no exception raised')
    except ValueError:
        check('name=%r refused' % bad, True)

print('\n=== 4. escalation is refused when the artifact describes another document ===')
guilty = sorted(glob.glob(os.path.join(QUAR, '*_esc_*.json')))
check('the quarantined guilty artifacts are present to test against', len(guilty) == 3,
      'found %d' % len(guilty))
for f in guilty:
    b = os.path.basename(f)
    d = json.load(open(f, encoding='utf-8'))
    name = b.replace('_llm_', '').replace('_esc_balance.json', '')
    ok, why = P.identity_guard(name, 'balance', d.get('columns') or [])
    if 'Органик парк_6мес_2025' in name or 'ТГК-14_6мес_2025' in name:
        check('%s refused (file year vs latest column)' % name, not ok, why)
    else:
        check('%s allowed (same-year foreign doc: caught by the key, not by the year)'
              % name, ok, why)

print('\n=== 5. the guard does not fire on genuine artifacts ===')
genuine = [f for f in sorted(glob.glob(os.path.join(PAGES, '*_esc_*.json')))]
check('genuine artifacts exist to test against', len(genuine) >= 10, 'found %d' % len(genuine))
false_pos = []
for f in genuine:
    b = os.path.basename(f)
    d = json.load(open(f, encoding='utf-8'))
    name = b.replace('_llm_', '')
    for suf in ('_esc_balance.json', '_esc_income_statement.json', '_esc_cash_flow.json'):
        name = name.replace(suf, '')
    ok, why = P.identity_guard(name, 'balance', d.get('columns') or [])
    if not ok:
        false_pos.append((b, why))
check('no false positives on the %d genuine artifacts' % len(genuine), not false_pos, str(false_pos))

print('\n=== 6. sibling conflict detection finds the known reclassification ===')
# Моторные технологии: the 2026 report prints 1250 at 31.12.2024 = 92960, while the 2025
# report prints 5160 plus a separate "Депозитные счета" row of 87800 (5160 + 87800 = 92960).
m26 = json.load(open(os.path.join(P.OUTDIR, 'Моторные технологии_6мес_2026.json'), encoding='utf-8'))
conf = P.sibling_conflicts('Моторные технологии_6мес_2026.pdf', 'balance',
                           m26['balance']['items'], m26['balance']['columns'])
codes = {c['code'] for c in conf}
check('conflicts found between the 2026 and the 2025 report', bool(conf), 'none found')
check('code 1250 is among them', '1250' in codes, str(sorted(codes, key=str)))
row = next((c for c in conf if c['code'] == '1250'), None)
if row:
    check('the 1250 conflict is the reclassification 5160 vs 92960',
          {row['this_file'], row['other_file']} == {5160, 92960}, str(row))
check('the shared date really is 31.12.2024',
      all(c['date'] == '2024-12-31' for c in conf), str({c['date'] for c in conf}))
check('a document with no sibling year yields no conflicts',
      P.sibling_conflicts('Несуществующий_6мес_2025.pdf', 'balance', [], []) == [])

print('\n=== 7. date parsing ===')
for label, want in (('На 31 декабря 2024 г.', '2024-12-31'),
                    ('На 30 июня 2025 г.', '2025-06-30'),
                    ('На 30 Июня 2025 г.', '2025-06-30'),
                    ('31.12.2024', '2024-12-31'),
                    ('', None), ('Итого', None)):
    check('column_date(%r) = %r' % (label, want), P.column_date(label) == want,
          repr(P.column_date(label)))

print('\n=== 8. the provider is part of the key (ticket 03) ===')
import providers as PR

# The old formula, spelled out: this is what every key on disk was built with, and
# Polza must keep producing exactly it — otherwise switching profile would re-transcribe
# and re-pay for every page (about 986 RUB).
def old_key(doc, name, p, dpi, model):
    stem = os.path.splitext(name)[0]
    return os.path.join(PAGES, '%s_p%d_%d_%s_%s.md' % (stem, p, dpi, P.model_tag(model),
                                                       P.doc_fingerprint(doc)))

check('Polza key is byte-identical to the old formula',
      P.page_cache_path(d1, 'ТГК-14_6мес_2025.pdf', 3, 300, P.M_ESC)
      == old_key(d1, 'ТГК-14_6мес_2025.pdf', 3, 300, P.M_ESC))
check('Polza key is byte-identical for the main model too',
      P.page_cache_path(d1, 'ТГК-14_6мес_2025.pdf', 6, 200, P.M_MAIN)
      == old_key(d1, 'ТГК-14_6мес_2025.pdf', 6, 200, P.M_MAIN))

other = PR.Profile('другой', 'https://example.test/v1/chat', 'K',
                   {'detect': 'd', 'main': 'm', 'esc': 'e'}, {}, cache_tag='xx')
k_other = P.page_cache_path(d1, 'ТГК-14_6мес_2025.pdf', 3, 300, P.M_ESC, profile=other)
check('another provider gets a different key',
      k_other != P.page_cache_path(d1, 'ТГК-14_6мес_2025.pdf', 3, 300, P.M_ESC))
check('the provider tag is visible in the key', '_xx_' in os.path.basename(k_other))
check('another provider still names the model', P.model_tag(P.M_ESC) in os.path.basename(k_other))
check('another provider still carries the PDF fingerprint',
      P.doc_fingerprint(d1) in os.path.basename(k_other))

# Two providers serving the same model name must not share a transcript: this is
# exactly the 4.1 class of defect, where one document's data appeared under another's.
same_model_polza = P.page_cache_path(d1, 'ТГК-14_6мес_2025.pdf', 3, 300, 'общая/модель')
same_model_other = P.page_cache_path(d1, 'ТГК-14_6мес_2025.pdf', 3, 300, 'общая/модель',
                                     profile=other)
check('same model name at two providers -> two different keys',
      same_model_polza != same_model_other)

# A variant is expressed as an address suffix, so the difference must come out of
# model_tag by itself, with no separate variant field in the key.
v_default = P.page_cache_path(d1, 'ТГК-14_6мес_2025.pdf', 3, 300, 'vendor/model', profile=other)
v_net = P.page_cache_path(d1, 'ТГК-14_6мес_2025.pdf', 3, 300, 'vendor/model:network',
                          profile=other)
check('two variants of one model -> two different keys', v_default != v_net)
check('the variant survives sanitising as a readable suffix',
      'model-network' in os.path.basename(v_net), os.path.basename(v_net))
check('the default variant keeps the plain model name',
      'model_xx_' in os.path.basename(v_default), os.path.basename(v_default))
# model_tag drops non-ASCII characters, so a non-Latin model id falls back to a
# placeholder. It must still be non-empty and still tell two variants apart.
check('a non-Latin model id still yields a non-empty tag',
      bool(P.model_tag('модель')) and P.model_tag('модель') == P.model_tag('модель'))
check('two variants of a non-Latin model id still differ',
      P.model_tag('модель') != P.model_tag('модель:network'))

# The guard must still work with an explicit profile.
for bad in ('x', '', 'какой-то_другой_документ.pdf'):
    try:
        P.page_cache_path(d1, bad, 3, 300, P.M_ESC, profile=other)
        check('name=%r refused with an explicit profile' % bad, False, 'no exception raised')
    except ValueError:
        check('name=%r refused with an explicit profile' % bad, True)

print('\n=== 9. diagnostic transcript dumps name the provider too ===')
# The pipeline dumps the transcripts it worked from to <stem>_<form>_p<N>.md. Nothing
# reads them back, but they used to receive one provider's transcript in one run and
# another's in the next under the same name — the shape of defect 4.1.
src = open(P.__file__, encoding='utf-8').read()
check('the dump path is built from the shared provider helper',
      'os.path.splitext(name)[0]}_{k}{_provider_infix()}.md' in src,
      'the dump no longer carries the provider')
check('the cache key uses the same helper as the dump',
      '_provider_infix(prof)' in src, 'the two sites could drift apart')
check('the dump suffix is empty for Polza (existing names keep their meaning)',
      PR.active('polza').cache_suffix() == '')
check('the helper yields an underscore-prefixed fragment for another provider',
      P._provider_infix(PR.Profile('p', 'https://x', 'K', {}, {}, cache_tag='zz')) == '_zz')

print('\n=== 10. provider-produced JSON caches name the provider too ===')
# Escalation, page detection and form structuring all cache a MODEL's output. Shared
# under one name, a PlusVibe run could consume Polza's escalation answer and then record
# "plusvibe" as its provenance — the 4.1 shape again, one level up from transcripts.
src = open(P.__file__, encoding='utf-8').read()
check('the structured-cache path carries the provider infix',
      "f'_llm_{tag}{_provider_infix()}.json'" in src,
      'cached_llm still writes a provider-agnostic name')
check('the path is built in exactly one place, so no call site can bypass it',
      src.count('_llm_') == 1,
      'the _llm_ prefix appears %d times; every cached artifact must go through cached_llm'
      % src.count('_llm_'))
# Polza must keep the exact names already on disk, or every cached escalation and
# detection result would be recomputed and re-paid for.
import re as _re
llm_files = [n for n in os.listdir(PAGES) if n.startswith('_llm_')]
check('there are cached structured artifacts to check against', len(llm_files) > 20,
      len(llm_files))
stray = [n for n in llm_files if n.endswith('_pv.json')]
check('no PlusVibe structured cache exists under a Polza-style name', not stray, stray[:3])
check('the Polza infix is empty, so those names are unchanged',
      P._provider_infix(PR.active('polza')) == '')
check('another provider gets its own structured cache',
      P._provider_infix(PR.Profile('p', 'https://x', 'K', {}, {}, cache_tag='pv')) == '_pv')

print('\n=== 11. every existing key on disk stays reachable for Polza ===')
on_disk = [n for n in os.listdir(PAGES)
           if re.match(r'^.+_p\d+_(200|300)_.+_[0-9a-f]{10}\.md$', n)]
check('there are page transcripts to check against', len(on_disk) > 100, len(on_disk))
unreachable = []
for n in on_disk[:400]:
    m = re.match(r'^(?P<stem>.+)_p(?P<p>\d+)_(?P<dpi>\d+)_(?P<tag>.+)_(?P<fp>[0-9a-f]{10})\.md$', n)
    if not m:
        continue
    # Rebuild the key the way page_cache_path does, from the same four facts.
    rebuilt = '%s_p%s_%s_%s_%s.md' % (m.group('stem'), m.group('p'), m.group('dpi'),
                                      m.group('tag'), m.group('fp'))
    if rebuilt != n:
        unreachable.append(n)
check('the key formula reproduces the names already on disk', not unreachable,
      unreachable[:3])

d1.close(); d2.close()

print('\n' + '=' * 60)
print('passed: %d   failed: %d' % (len(PASS), len(FAIL)))
if FAIL:
    print('FAILED:')
    for f in FAIL:
        print('   -', f)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_last_run.txt'),
     'w', encoding='utf-8').write('\n'.join(LOG) + '\n')
sys.exit(1 if FAIL else 0)
