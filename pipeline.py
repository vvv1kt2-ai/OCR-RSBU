# -*- coding: utf-8 -*-
r"""Pilot pipeline: extract RSBU forms (balance, income statement, cash flow) from PDFs.
Two branches: text-layer -> rule parser; scans -> vision-LLM via polza.ai.
Router/escalation logic per D:\models\agent_task_extraction.md section 4.0.
"""
import sys, os, re, json, copy, base64, time, hashlib, urllib.request, urllib.error

sys.path.insert(0, 'D:/models/pylibs')
import pymupdf

DOWNLOADS = r'D:\data-scraping\downloads'
OUTDIR    = os.environ.get('PILOT_OUTDIR', r'D:\models\extracted')
PAGESDIR  = os.path.join(OUTDIR, 'pages')
CRED      = r'C:\Users\1\.dsh\.credentials.yaml'
BASE      = 'https://polza.ai/api/v1/chat/completions'

# model -> (prompt RUB/1M, completion RUB/1M)  from polza catalog 2026-07
PRICES = {
    'google/gemini-2.5-flash-lite': (12.2164, 48.8656),
    'google/gemini-2.5-flash':      (21.20418, 176.7015),
    'google/gemini-3.8-flash':      (45.8115, 229.0575),
    'anthropic/claude-sonnet-5':    (244.328, 1221.64),
}
M_DETECT = 'google/gemini-2.5-flash-lite'
M_MAIN   = 'google/gemini-3.8-flash'
M_ESC    = 'anthropic/claude-sonnet-5'

USAGE = {'calls': 0, 'prompt': 0, 'completion': 0, 'cost_rub': 0.0}

# --- поставщик как профиль -------------------------------------------------
# Три роли моделей остаются теми же именами (внешние скрипты и тесты их импортируют),
# но их значения теперь берутся из профиля, а не вписаны здесь.
import providers as _providers

_PROVIDER = _providers.register(_providers.Profile(
    name='polza',
    chat_url=BASE,
    key_name='POLZA_API_KEY',
    roles={'detect': M_DETECT, 'main': M_MAIN, 'esc': M_ESC},
    prices=PRICES,
    cache_tag='',
    cost_header=None,
    note='встроенный профиль: адреса моделей уже лежат в коде, ключи кэша прежние'))

ACTIVE_PROFILE = _providers.active()
BASE     = ACTIVE_PROFILE.chat_url
M_DETECT = ACTIVE_PROFILE.roles['detect']
M_MAIN   = ACTIVE_PROFILE.roles['main']
M_ESC    = ACTIVE_PROFILE.roles['esc']
PRICES   = ACTIVE_PROFILE.prices

def load_key():
    return _providers.load_key(ACTIVE_PROFILE)

KEY = load_key()

# A reasoning model spends part of max_tokens on its own reasoning before it emits any
# answer, and the provider bills that reasoning as output. When the limit is too small the
# limit runs out before the answer starts and the call comes back as an error with no text:
# «Поставщик вернул ответ без текста: весь заданный вами max_tokens ушёл на внутренние
# рассуждения модели». Retrying the same call with the same limit cannot help, so `chat()`
# recognises this one condition and retries with twice the room instead.
REASONING_STARVED_MARKERS = ('рассужд', 'internal reasoning', 'reasoning tokens')
REASONING_HEADROOM_CAP = 32000   # matches the largest limit already used in this file


def _reasoning_starved(raw):
    """True when the provider says the whole max_tokens went into reasoning."""
    if not raw:
        return False
    try:
        t = raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else str(raw)
    except Exception:
        return False
    t = t.lower()
    return 'max_tokens' in t and any(m in t for m in REASONING_STARVED_MARKERS)


def chat(messages, model, temperature=0.1, max_tokens=8192, retries=2, timeout=240):
    last = None
    limit = max_tokens
    for attempt in range(retries + 1):
        # rebuilt each attempt: a reasoning-starved retry asks for more room
        url, headers, body = _providers.build_request(
            ACTIVE_PROFILE, model, messages, KEY, temperature, limit)
        try:
            req = urllib.request.Request(url, data=body, method='POST', headers=headers)
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
                resp_headers = r.headers
            u = data.get('usage') or {}
            pt, ct = u.get('prompt_tokens', 0), u.get('completion_tokens', 0)
            cost, cost_src = _providers.call_cost(ACTIVE_PROFILE, model, pt, ct, resp_headers)
            USAGE['calls'] += 1; USAGE['prompt'] += pt; USAGE['completion'] += ct
            USAGE['cost_rub'] += cost
            txt = data['choices'][0]['message']['content'] or ''
            fin = data['choices'][0].get('finish_reason')
            print(f'  [llm] {model} pt={pt} ct={ct} cost={cost:.2f}RUB ({cost_src}) '
                  f'{time.time()-t0:.0f}s finish={fin}')
            if not txt.strip() and fin == 'length' and limit < REASONING_HEADROOM_CAP:
                # same condition, but reported as a truncated empty answer rather than
                # an error: the limit was spent before any text was produced
                last = f'empty answer with finish=length at max_tokens={limit}'
                print(f'  [llm] attempt {attempt+1} gave no text (finish=length) '
                      f'-> retrying with max_tokens={min(limit * 2, REASONING_HEADROOM_CAP)}')
                limit = min(limit * 2, REASONING_HEADROOM_CAP)
                time.sleep(2)
                continue
            return txt, fin
        except urllib.error.HTTPError as e:
            raw = e.read()
            last = f'HTTP {e.code}: {raw[:400]}'
            print(f'  [llm] attempt {attempt+1} failed: {last}')
            if _reasoning_starved(raw) and limit < REASONING_HEADROOM_CAP:
                limit = min(limit * 2, REASONING_HEADROOM_CAP)
                print(f'  [llm] reasoning ate the whole limit -> retrying with '
                      f'max_tokens={limit}')
        except Exception as e:
            last = str(e); print(f'  [llm] attempt {attempt+1} failed: {last}')
        time.sleep([2, 8, 30][min(attempt, 2)])
    raise RuntimeError(f'LLM failed after retries: {last}')

def parse_num(s):
    """'12 112'->12112, '(1 345)'->-1345, '-'/''/None->None, '1,5'->1.5"""
    if s is None: return None, None
    raw = s.replace('\u00a0', ' ').replace('\u202f', ' ').strip()
    if raw in ('', '-', '–', '—', 'Х', 'х', 'x'): return None, raw
    neg = raw.startswith('(') and raw.endswith(')')
    core = raw[1:-1] if neg else raw
    core = core.replace(' ', '').replace(',', '.')
    if not re.fullmatch(r'-?\d+(\.\d+)?', core): return None, raw
    v = float(core)
    v = -v if neg else v
    return (int(v) if v == int(v) else v), raw

def extract_json(txt):
    t = re.sub(r'^```(json)?|```$', '', txt.strip(), flags=re.M).strip()
    a, b = t.find('{'), t.rfind('}')
    if a < 0 or b < 0: raise ValueError('no json in llm output')
    return json.loads(t[a:b + 1])

def render_png(page, dpi):
    pix = page.get_pixmap(dpi=dpi)
    import base64 as _b
    return _b.b64encode(pix.tobytes('png')).decode()

def img_message(b64, text):
    return {'role': 'user', 'content': [
        {'type': 'text', 'text': text},
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + b64}}]}

def img_parts(b64, text):
    """content parts to append into an existing message (multi-image calls)"""
    return [{'type': 'text', 'text': text},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + b64}}]

# ---------------------------------------------------------------- text branch
FORMS = {'0710001': 'balance', '0710002': 'income_statement', '0710005': 'cash_flow'}
MONTHS = {'января':1,'февраля':2,'марта':3,'апреля':4,'мая':5,'июня':6,'июля':7,
          'августа':8,'сентября':9,'октября':10,'ноября':11,'декабря':12}

def find_form_pages(doc):
    """map form_key -> list of 1-based pages.
    Start page = first page containing form code or title; continuation = pages
    up to next form start (capped +4), excluding pages of other sections.
    Strict start: a bare title mention is not enough (row names and 'ПОЯСНЕНИЯ
    К БУХГАЛТЕРСКОМУ БАЛАНСУ' must not start a form) — page must look like the form."""
    CODES = {'balance': '0710001', 'income_statement': '0710002', 'cash_flow': '0710005'}
    TITLES = {'balance': ['Бухгалтерский баланс'],
              'income_statement': ['Отчет о финансовых результатах', 'Отчёт о финансовых результатах'],
              'cash_flow': ['Отчет о движении денежных средств', 'Отчёт о движении денежных средств']}
    SKIP = ['Отчет об изменениях капитала', 'Отчёт об изменениях капитала',
            'Пояснения к бухгалтерскому', 'Отчет о целевом использовании']
    def _strict_start(key, t):
        if CODES[key] in t: return True
        tl = t.lower()
        if key == 'balance':
            return 'Бухгалтерский баланс' in t and ('АКТИВ' in t or 'ПАССИВ' in t)
        if key == 'income_statement':
            return 'финансовых результатах' in tl and ('Наименование показателя' in t or 'Выручка' in t)
        return 'движении денежных средств' in tl and ('Наименование показателя' in t or 'Сальдо денежных потоков' in t)
    starts = {}
    for i, pg in enumerate(doc):
        t = pg.get_text()
        for key in CODES:
            if key not in starts and _strict_start(key, t):
                starts[key] = i + 1
    OTHER = {k: (v, TITLES[k]) for k, v in CODES.items()}
    BAL_CODES = {'1100', '1110', '1150', '1160', '1170', '1180', '1190', '1200',
                 '1210', '1220', '1230', '1240', '1250', '1260', '1300', '1310',
                 '1360', '1370', '1400', '1410', '1420', '1430', '1450', '1500',
                 '1510', '1520', '1530', '1540', '1550', '1600', '1700'}
    def _form_code_hits(key, t):
        return len(BAL_CODES & set(re.findall(r'\d{4}', t))) if key == 'balance' else 0
    out = {}
    for key, s in starts.items():
        pages, p, misses = [], s, 0
        while p <= len(doc) and misses < 3:
            t = doc[p - 1].get_text()
            if any(m in t for m in SKIP) and CODES[key] not in t and _form_code_hits(key, t) < 3: break
            other = any((CODES[k] in t or any(ti in t for ti in TITLES[k]))
                        for k in OTHER if k != key)
            if CODES[key] in t or any(ti in t for ti in TITLES[key]) or _form_code_hits(key, t) >= 3:
                pages.append(p); misses = 0
            elif other and _form_code_hits(key, t) < 3:
                break
            elif not pages:
                break
            else:
                # no form marker: keep the page only if it is table content
                # (row names + numbers), not prose; stop at signature blocks
                lines = [x.strip() for x in t.splitlines() if x.strip()]
                nval = sum(1 for x in lines if is_value_line(x) or CODE_RE.match(x))
                nprose = sum(1 for x in lines if len(x) > 70)
                if any(re.match(r'(Директор|Главный бухгалтер|Руководитель)\b', x) for x in lines):
                    break
                if nval >= 6 and nprose <= 2:
                    pages.append(p); misses = 0
                else:
                    misses += 1
            p += 1
        # back-extension: form may start on an earlier page whose header OCR
        # mangled the title/code (e.g. asset section before the page carrying 0710001)
        for _ in range(2):
            if not pages or pages[0] <= 1: break
            t = doc[pages[0] - 2].get_text()
            tl = t.lower()
            if any(m in t for m in SKIP) or any(CODES[k] in t for k in CODES if k != key): break
            if _form_code_hits(key, t) >= 3:
                pages.insert(0, pages[0] - 1); continue
            lead = {'balance': ('актив' in tl or 'баланс' in tl),
                    'income_statement': ('выручка' in tl or 'Наименование показателя' in t),
                    'cash_flow': ('сальдо' in tl or 'Наименование показателя' in t)}.get(key, False)
            lines = [x.strip() for x in t.splitlines() if x.strip()]
            nval = sum(1 for x in lines if is_value_line(x) or CODE_RE.match(x))
            if lead and nval >= 6:
                pages.insert(0, pages[0] - 1)
            else:
                break
        out[key] = pages
    return out

TERMINAL_CODE = {'balance': '1700', 'income_statement': '2400', 'cash_flow': '4500'}
TERMINAL_ALT = {'cash_flow': ('4400',)}

def codes_deep(items):
    """every 4-digit code in a form, children included"""
    out = set()
    for it in items or []:
        c = str(it.get('code') or '')
        if c: out.add(c)
        out |= codes_deep(it.get('children'))
    return out

def form_is_complete(form_key, items):
    """False when the form stops before its closing total row.

    The balance's passive side sits on the page after the asset side. When that
    page is image-only, find_form_pages cannot see it, the form ends at 1600 and
    '1600 == 1700' fails in every column (defect 4.2). Same shape for 2400/4500.
    """
    term = TERMINAL_CODE.get(form_key)
    if not term:
        return True
    cs = codes_deep(items)
    if term in cs:
        return True
    return any(a in cs for a in TERMINAL_ALT.get(form_key, ()))

def extra_form_pages(doc, used, max_extra=3):
    """Image-only pages immediately after the last used page of a form.

    A mixed PDF (some pages carry a text layer, some are pure scans) hides the
    continuation of a form from the text branch: those pages have no text, so
    find_form_pages never returns them.
    """
    out = []
    p = (used[-1] if used else 0) + 1
    while p <= len(doc) and len(out) < max_extra:
        pg = doc[p - 1]
        if len(pg.get_text().strip()) >= 50 or not pg.get_images():
            break
        out.append(p)
        p += 1
    return out

def n_checks_ok(form_key, items):
    """how many arithmetic identities this item set satisfies (quality metric)"""
    try:
        return sum(1 for c in run_checks(form_key, items) if c.get('ok'))
    except Exception:
        return -1

def detect_columns(text):
    """column labels from header text: 3 balance dates or 2 period labels"""
    dates = []
    for d, mon, y in re.findall(r'На\s+(\d{1,2})\s+([а-яё]+)\s+(\d{4})', text, re.I):
        m = MONTHS.get(mon.lower())
        if m:
            iso = f'{y}-{m:02d}-{int(d):02d}'
            if iso not in dates: dates.append(iso)
    if len(dates) >= 2: return dates[:3]
    pers = []
    for a, b in re.findall(r'За\s+((?:\d+\s+)?(?:полугодие|месяцев|месяц|квартал|год)[а-яё]*)\s+(\d{4})', text, re.I):
        lab = f'За {a} {b} г.'
        if lab not in pers: pers.append(lab)
    return pers[:2]

NOISE_RE = re.compile(r'^(Форма 0|с\.\s*\d|Пояснения$|Наименование показателя$|Код$|На\s+\d{1,2}\s|Отчетная дата|\(число|\(наименование|\(подпись|\(расшифровка|0\d{5,}$|За\s+[\d\s]*(?:полугодие|месяц|квартал|месяцев|год)[а-яё]*\s*$)', re.I)
YEAR_RE = re.compile(r'^\d{4}\s*г\.?\s*$')
GRP_RE = re.compile(r'^[IVX]+\.\s+\S')
CODE_RE = re.compile(r'^\d{4}$')
GATE_RE = re.compile(r'^(Наименование показателя|Пояснения)$')
STOP_RE = re.compile(r'^(Директор|Главный бухгалтер|Руководитель|Бухгалтер)\b')
KNOWN_TOP = set('''1110 1150 1160 1170 1180 1190 1100 1210 1215 1220 1230 1240 1250 1260 1200 1600
1310 1320 1340 1350 1360 1365 1370 1300 1410 1420 1430 1440 1450 1400 1510 1520 1530 1540 1550 1500 1700
2110 2120 2100 2210 2220 2200 2310 2320 2330 2340 2350 2300 2410 2420 2421 2430 2450 2460 2400 2510 2520 2530 2500 2900 2910
4110 4111 4112 4113 4114 4119 4120 4121 4122 4123 4124 4129 4100 4210 4211 4212 4213 4214 4219 4220 4221 4222 4223 4224 4229 4200
4310 4311 4312 4313 4314 4319 4320 4321 4322 4323 4329 4300 4400 4450 4490 4500'''.split())

def is_value_line(s):
    if s == '-': return True
    if re.fullmatch(r'\(-?[\d\s]+([,\.]\d+)?\)', s): return True
    if re.fullmatch(r'-?[\d\s]+([,\.]\d+)?', s) and any(ch.isdigit() for ch in s): return True
    return False

def structure_text_form(doc, pages, form_key):
    """Linear parse of raw text: name -> [4-digit code] -> value columns.
    '(1 345)' = negative; '-' = null. Detail rows (no code) become children."""
    warnings = []
    lines = []
    for p in pages:
        lines.extend(doc[p - 1].get_text().splitlines())
    columns = detect_columns('\n'.join(lines[:120]))
    ncols = len(columns) or 2
    if not columns: warnings.append('columns not detected, assumed 2')

    items, current = [], None
    section = group = None
    started = False
    st = {'pending': [], 'code': None, 'values': [], 'child_next': False}

    def flush():
        nonlocal current
        if not st['pending'] and st['code'] is None and not st['values']: return
        name = re.sub(r'\s+', ' ', ' '.join(st['pending'])).strip()
        vals = [v for v, _ in st['values']] + [None] * ncols
        raws = [r for _, r in st['values']] + [''] * ncols
        vals, raws = vals[:ncols], raws[:ncols]
        if name or st['code'] is not None:
            top = st['code'] in KNOWN_TOP if st['code'] else False
            is_child = (not top) and current is not None
            if is_child:
                current.setdefault('children', []).append(
                    {'name': name, 'code': st['code'],
                     'values': vals, 'raw_values': raws})
            else:
                item = {'code': st['code'], 'name': name, 'section': section,
                        'group': group, 'values': vals, 'raw_values': raws}
                items.append(item); current = item
                if len(st['values']) == 0:
                    warnings.append(f'row without values: {st["code"]} {name[:40]}')
        st['pending'] = []; st['code'] = None; st['values'] = []; st['child_next'] = False

    for ln in lines:
        s = ln.replace('\u00a0', ' ').replace('\u202f', ' ').strip()
        if not s: continue
        if not structure_text_form._started:
            if GATE_RE.match(s): structure_text_form._started = True
            else: continue
        if STOP_RE.match(s): break
        if NOISE_RE.search(s) or YEAR_RE.match(s): continue
        if s in ('АКТИВ', 'ПАССИВ'):
            section = s; flush(); group = None; continue
        if GRP_RE.match(s) and not is_value_line(s):
            group = s; flush(); continue
        if s.lower().startswith('в том числе'):
            flush(); st['child_next'] = True; continue
        if CODE_RE.match(s) and st['code'] is None and not st['values']:
            # continuation-child (e.g. 2412 after 2411): next code right after a child code
            st['code'] = s
            if not st['pending'] and current is not None and st['child_next']:
                pass  # name will be picked up on next lines
            continue
        if is_value_line(s):
            if st['code'] is None and not st['pending']:  # stray value
                continue
            st['values'].append(parse_num(s))
            if len(st['values']) == ncols: flush()
            continue
        if st['values'] or (st['code'] is not None): flush()   # new row begins
        st['pending'].append(s)
    flush()
    structure_text_form._started = False
    return columns, items, warnings

structure_text_form._started = False

# ---------------------------------------------------------------- checks
def val_map(items):
    m = {}
    for it in items:
        if it.get('code'): m[it['code']] = it['values']
    return m

def col_check(m, code, fn, ncols):
    out = []
    for c in range(ncols):
        v = m.get(code)
        if v is None or c >= len(v) or v[c] is None:
            out.append(None); continue
        try: out.append(bool(fn(m, c)))
        except Exception: out.append(None)
    return out

def run_checks(form_key, items):
    m = val_map(items)
    n = max((len(it['values']) for it in items if it['values']), default=0)
    res = []
    def S(code, c): return m.get(code, [None]*n)[c] if c < len(m.get(code, [])) else None
    TOL = 2  # tolerance for rounding differences
    def eq(a, b): return a is not None and b is not None and abs(a - b) <= TOL
    def nz(*xs): return sum(x for x in xs if x is not None)
    def has(*xs): return any(x is not None for x in xs)
    if form_key == 'balance':
        rules = [
            ('1600 == 1700', lambda c: eq(S('1600', c), S('1700', c)) if has(S('1600', c)) else None),
            # Sub-lines 1120/1130/1140 belong to section I: without them the sum is short
            # whenever a filer uses them. They are empty in the current corpus, so the
            # omission is latent here — but a missing code turns into a FALSE failure,
            # and a false failure buys an escalation (pipeline.py:1050). Same for 1215
            # below, which is why it is listed: it cost 16 escalation pages on КЛВЗ.
            ('1100 == 1110+1120+1130+1140+1150+1160+1170+1180+1190', lambda c: eq(S('1100', c), nz(*[S(k, c) for k in ('1110','1120','1130','1140','1150','1160','1170','1180','1190')])) if has(S('1100', c)) else None),
            ('1200 == 1210+1215+1220+1230+1240+1250+1260', lambda c: eq(S('1200', c), nz(*[S(k, c) for k in ('1210','1215','1220','1230','1240','1250','1260')])) if has(S('1200', c)) else None),
            ('1300+1400+1500 == 1700', lambda c: eq(nz(S('1300', c), S('1400', c), S('1500', c)), S('1700', c)) if has(S('1700', c)) else None),
        ]
    elif form_key == 'income_statement':
        def diff_rule(name, expected_fns, actual_fn):
            # accept any of the expected variants (sign conventions / optional lines)
            def fn(c):
                a = actual_fn(c)
                if a is None: return None
                for ef in expected_fns:
                    e = ef(c)
                    if e is None: continue
                    if a == e or a == -e: return True
                return False
            return name, fn
        rules = [
            diff_rule('2100 == 2110-2120 (±)',
                      [lambda c: (S('2110', c) or 0) - abs(S('2120', c) or 0) if has(S('2110', c), S('2120', c)) else None],
                      lambda c: S('2100', c)),
            diff_rule('2200 == 2100-2210-2220 (±)',
                      [lambda c: (S('2100', c) or 0) - abs(S('2210', c) or 0) - abs(S('2220', c) or 0) if has(S('2100', c)) else None],
                      lambda c: S('2200', c)),
            diff_rule('2400 == 2300-2410±2421∓2430±2450-2460',
                      [lambda c: (S('2300', c) or 0)-(S('2410', c) or 0)+(S('2421', c) or 0)-(S('2430', c) or 0)+(S('2450', c) or 0)-(S('2460', c) or 0) if has(S('2300', c)) else None,
                       lambda c: (S('2300', c) or 0)+(S('2410', c) or 0)-(S('2421', c) or 0)+(S('2430', c) or 0)-(S('2450', c) or 0)+(S('2460', c) or 0) if has(S('2300', c)) else None],
                      lambda c: S('2400', c)),
        ]
    else:
        rules = [
            ('4400 == 4100+4200+4300', lambda c: eq(S('4400', c), nz(S('4100', c), S('4200', c), S('4300', c))) if has(S('4400', c)) else None),
            ('4500 == 4450+4400+4490', lambda c: eq(S('4500', c), nz(S('4450', c), S('4400', c), S('4490', c))) if has(S('4500', c)) else None),
        ]
    for name, fn in rules:
        per_col = []
        for c in range(n):
            try: per_col.append(fn(c))
            except Exception: per_col.append(None)
        ok = all(v is not False for v in per_col) and any(v is True for v in per_col)
        res.append({'rule': name, 'per_column': per_col, 'ok': ok})
    return res

# ---------------------------------------------------------------- LLM structuring
SCHEMA_HINT = '''Верни СТРОГО JSON без пояснений по схеме:
{"columns": ["<дата/период колонки 1>", ...],
 "items": [{"code": "1110", "name": "Нематериальные активы", "values": [v1, v2, ...],
            "children": [{"name": "...", "values": [...]}]}, ...]}
Правила: numbers как в документе (тыс руб), прочерк/пусто -> null, "(123)" -> -123,
разделители тысяч игнорируй. Каждая строка таблицы = один элемент items в порядке следования.
Строки "в том числе" -> в children предыдущего элемента. НЕ выдумывай значения.'''

def llm_structure_form(transcript, form_key, model=None):
    fname = {'balance': 'Бухгалтерский баланс (0710001)',
             'income_statement': 'Отчет о финансовых результатах (0710002)',
             'cash_flow': 'Отчет о движении денежных средств (0710005)'}[form_key]
    prompt = (f'Ниже транскрипция страниц отчетности: {fname}.\n'
              f'Структурируй в JSON. {SCHEMA_HINT}\n\nТРАНСКРИПЦИЯ:\n{transcript}')
    def _call():
        txt, fin = chat([{'role': 'user', 'content': prompt}], model or M_MAIN, temperature=0, max_tokens=32000)
        if fin == 'length':
            raise ValueError('structuring truncated (finish=length)')
        return extract_json(txt)
    return _call(), None

def _nk(s):
    """normalized row name for matching: lowercase letters/digits only"""
    return re.sub(r'[^a-zа-яё0-9]', '', (s or '').lower())

# canonical balance row names (normalized) -> candidate codes in document order
BAL_NAMES = {
    'нематериальныеактивы': ['1110'],
    'основныесредства': ['1150'],
    'доходныевложениявматериальныеценности': ['1160'],
    'финансовыевложения': ['1170', '1240'],
    'финансовыевложениязаисключениемденежныхэквивалентов': ['1240'],
    'отложенныеналоговыеактивы': ['1180'],
    'прочиевнеоборотныеактивы': ['1190'],
    'итогопоразделуi': ['1100'], 'итоговнеоборотныеактивы': ['1100'],
    'запасы': ['1210'],
    'налогнадобавленнуюстоимостьпоприобретеннымценностям': ['1220'],
    'дебиторскаязадолженность': ['1230'],
    'денежныесредстваиденежныеэквиваленты': ['1250'],
    'прочиеоборотныеактивы': ['1260'],
    'итогопоразделуii': ['1200'], 'итогооборотныеактивы': ['1200'],
    'баланс': ['1600', '1700'],
    'уставныйкапитал': ['1310'],
    'переоценкавнеоборотныхактивов': ['1340'],
    'добавочныйкапитал': ['1350'],
    'резервныйкапитал': ['1360'],
    'нераспределеннаяприбыльнепокрытыйубыток': ['1370'],
    'итогопоразделуiii': ['1300'], 'итогокапитал': ['1300'],
    'заемныесредства': ['1410', '1510'],
    'отложенныеналоговыеобязательства': ['1420'],
    'оценочныеобязательства': ['1430', '1540'],
    'прочиеобязательства': ['1450', '1550'],
    'итогопоразделуiv': ['1400'], 'итогодолгосрочныеобязательства': ['1400'],
    'кредиторскаязадолженность': ['1520'],
    'итогопоразделуv': ['1500'], 'итогократкосрочныеобязательства': ['1500'],
}

def _assign_bal_codes(items):
    """assign canonical codes to codeless balance rows by name (queue per name, doc order)"""
    used = {it.get('code') for it in items if it.get('code')}
    def _one(rec):
        if rec.get('code'): return
        for c in BAL_NAMES.get(_nk(rec.get('name'))) or []:
            if c not in used:
                rec['code'] = c; used.add(c); return
    for it in items: _one(it)
    for it in items:
        for ch in it.get('children') or []: _one(ch)

def _values_count(items):
    n = 0
    for it in items:
        n += sum(1 for v in (it.get('values') or []) if v is not None)
        for ch in it.get('children') or []:
            n += sum(1 for v in (ch.get('values') or []) if v is not None)
    return n

def _normalize_llm(llm, form_key=None):
    """LLM items -> normalized items; duplicate/non-canonical top-level codes become children"""
    raw = llm.get('items', [])
    if form_key == 'balance': _assign_bal_codes(raw)
    items, seen = [], set()
    for it in raw:
        code = it.get('code')
        rec = {'code': code, 'name': it.get('name'),
               'values': it.get('values'),
               'raw_values': it.get('raw_values', it.get('values')),
               'children': it.get('children', []) or []}
        if code and code in KNOWN_TOP and code not in seen:
            seen.add(code); items.append(rec)
        elif items:
            items[-1].setdefault('children', []).append(rec)
        else:
            items.append(rec)
    return items

# ---------------------------------------------------------------- scan branch
DETECT_PROMPT = ('Даны страницы PDF по порядку (последняя строка каждого приложения = номер страницы). '
                 'Определи для каждой страницы РОВНО одну категорию: '
                 'balance (Бухгалтерский баланс, 0710001), income_statement (Отчет о финансовых результатах, 0710002), '
                 'cash_flow (Отчет о движении денежных средств, 0710005), '
                 'notes (ПОЯСНЕНИЯ к балансу и отчёту: текстовые страницы с расшифровками — состав основных средств, '
                 'запасов, дебиторской и кредиторской задолженности, связанные стороны, события после отчётной даты), '
                 'audit (АУДИТОРСКОЕ ЗАКЛЮЧЕНИЕ: текст с мнением аудитора, подписями, названием аудиторской организации; '
                 'в полугодовой отчётности его обычно нет, в годовой оно идёт ДО баланса, то есть баланс может начинаться не с 1-й страницы), '
                 'other (титульный лист, прочее). '
                 'Продолжение формы (в шапке "Форма 07100XX с. N") = та же форма. '
                 'ВАЖНО: страницы пояснений и аудиторского заключения НЕ относи к формам, даже если на них '
                 'встречаются названия и числа строк баланса — это отдельные текстовые документы, а не форма 07100XX. '
                 'Ответь ОДНОЙ строкой строго в формате {"1":"other","2":"balance",...} без пояснений.')

# The detection prompt is part of the artifact it produces: rewording it changes the labels,
# but the cache key did not include the prompt, so a rewritten prompt silently kept returning
# the OLD labels for every document already detected — the fix would look applied and do
# nothing. Bump this whenever DETECT_PROMPT changes, and expect one paid re-detection pass
# (detection is the cheap stage: 0.22 ₽ for the 41-document pilot).
DETECT_PROMPT_VERSION = 'v2'
FORM_LABELS = ('balance', 'income_statement', 'cash_flow')
PAGE_LABELS = FORM_LABELS + ('notes', 'audit', 'other')

def salvage_pages_map(txt, npages):
    """recover page->form mapping from truncated/broken JSON output"""
    out = []
    for m in re.finditer(r'"(\d{1,3})"\s*:\s*"(\w+)"', txt):
        p, f = int(m.group(1)), m.group(2)
        if 1 <= p <= npages and f in PAGE_LABELS:
            out.append({'page': p, 'form': f})
    return out

TRANSCRIBE_PROMPT = ('Транскрибируй таблицу со страницы бухгалтерской отчетности ДОСЛОВНО в Markdown. '
                     'Правила: каждое число точно как напечатано (с пробелами-разделителями тысяч, скобками, прочерками "-"); '
                     'не вычисляй, не исправляй, не добавляй комментариев; сохрани заголовок формы, шапку колонок и все строки.')

MONTHS_RU = {'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
             'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11,
             'декабря': 12}

def column_date(label):
    """'На 31 декабря 2024 г.' -> '2024-12-31'; None when the label is not a date."""
    s = re.sub(r'\s+', ' ', str(label or '')).strip()
    m = re.search(r'(\d{1,2})\s+([А-Яа-яЁё]+)\s+(\d{4})', s)
    if m and m.group(2).lower() in MONTHS_RU:
        return '%s-%02d-%02d' % (m.group(3), MONTHS_RU[m.group(2).lower()], int(m.group(1)))
    m = re.search(r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})', s)
    if m:
        return '%s-%02d-%02d' % (m.group(3), int(m.group(2)), int(m.group(1)))
    return None

def file_year(name):
    """'ТГК-14_6мес_2025.pdf' -> '2025'"""
    m = re.search(r'_(\d{4})(?:\.pdf)?$', str(name or ''), re.I)
    return m.group(1) if m else None

def _index_items(items):
    out = {}
    for it in items or []:
        for rec in [it] + (it.get('children') or []):
            out.setdefault((rec.get('code'), (rec.get('name') or '').strip()), rec)
    return out

def identity_guard(name, form_key, columns):
    """Blocking check: an escalation artifact must describe THIS document.

    The artifact carries column headers. For a `*_6мес_YYYY` report the LATEST column is
    the reporting date itself (30.06.YYYY); anything else means the page belongs to a
    different document. That is exactly how defect 4.1 reached the result JSONs:
    `Органик парк_6мес_2025` was escalated from Корпсан's pages, whose latest column is
    30.06.2026. Note that "YYYY appears among the column years" is NOT enough — the 2026
    artifact lists 2024, 2025 and 2026, so it also contains 2025.

    Costs nothing, fires on 2 of the 3 contaminated artifacts, no false positives on the
    current corpus (see _identity_check.py detector A).
    Returns (ok, reason).
    """
    want = file_year(name)
    dated = sorted({column_date(c) for c in (columns or []) if column_date(c)})
    if not want:
        return True, 'год файла не определён — проверка пропущена'
    if not dated:
        return True, 'в артефакте нет распознаваемых дат — проверка пропущена'
    latest = dated[-1]
    if latest[:4] != want:
        return False, (f'артефакт эскалации описывает другой документ: файл за {want} год, '
                       f'а последняя колонка артефакта — {latest}')
    return True, f'последняя колонка артефакта {latest} соответствует файлу за {want} год'

def sibling_conflicts(name, form_key, items, columns):
    """Advisory check: values on a date shared with the same emitter's other-year result.

    Every pair of files (emitter_6мес_2025, emitter_6мес_2026) shares one balance date
    (31.12 of the earlier year). Those two numbers must be equal. A conflict is either an
    extraction error or a genuine restatement in the later report, so this does NOT block:
    on the current corpus 70 rows conflict and at least one is a real reclassification
    (Моторные технологии: 5160 + deposit 87800 = 92960, printed differently in each
    report). Recorded as a warning for review.
    """
    m = re.match(r'^(.*)_6мес_(\d{4})(?:\.pdf)?$', str(name or ''), re.I)
    if not m:
        return []
    stem, year = m.group(1), m.group(2)
    other = {'2025': '2026', '2026': '2025'}.get(year)
    if not other:
        return []
    sib = os.path.join(OUTDIR, f'{stem}_6мес_{other}.json')
    if not os.path.exists(sib):
        return []
    try:
        sres = (json.load(open(sib, encoding='utf-8')).get(form_key) or {})
    except Exception:
        return []
    def dated(cols):
        out = {}
        for i, c in enumerate(cols or []):
            d = column_date(c)
            if d:
                out.setdefault(d, i)
        return out
    mine_d, sib_d = dated(columns), dated(sres.get('columns'))
    shared = sorted(set(mine_d) & set(sib_d))
    if not shared:
        return []
    mine, theirs = _index_items(items), _index_items(sres.get('items'))
    out = []
    for key in sorted(set(mine) & set(theirs), key=lambda x: (str(x[0]), x[1])):
        a = mine[key].get('values') or []
        b = theirs[key].get('values') or []
        for d in shared:
            ia, ib = mine_d[d], sib_d[d]
            if len(a) <= ia or len(b) <= ib:
                continue
            if a[ia] is None or b[ib] is None or a[ia] == b[ib]:
                continue
            out.append({'code': key[0], 'name': key[1], 'date': d,
                        'this_file': a[ia], 'other_file': b[ib]})
    return out

def escalate_failed_form(doc, form_key, result, warnings, name):
    """Re-OCR problem pages at 300 dpi with a stronger model, merge, re-check."""
    res = result[form_key]
    def codes_from_checks(chks):
        out = set()
        for c in chks:
            if c.get('ok'): continue
            for tok in re.findall(r'(?<![\d-])\d{4}(?![\d-])', c['rule']):
                out.add(tok)
        return out
    want = codes_from_checks([c for c in result['checks'] if c['form'] == form_key])
    pages = res.get('transcript_pages') or []
    if len(pages) > 8:   # cost guard: escalation never re-OCRs more than 8 pages
        print(f'  escalate: {len(pages)} pages listed, capping to first 8')
        pages = pages[:8]
    if not want or not pages: return
    print(f'  escalate {form_key}: codes={sorted(want)} pages={pages} -> {M_ESC} @300dpi')
    parts = []
    for p in pages:
        txt = transcribe_cached(doc, p, name=name, dpi=300, model=M_ESC)
        parts.append(f'=== СТРАНИЦА {p} ===\n{txt}')
    transcript = '\n\n'.join(parts)
    def _esc_struct(): return llm_structure_form(transcript, form_key, model=M_ESC)[0]
    llm = cached_llm(f'{name}_esc_{form_key}_{model_tag(M_ESC)}', _esc_struct)
    fresh = _normalize_llm(llm, form_key)
    # --- identity guards: an escalation may only speak about THIS document ---
    ok, why = identity_guard(name, form_key, llm.get('columns') or [])
    print(f'  escalate identity: {"OK" if ok else "REFUSED"} — {why}')
    if not ok:
        warnings.append(f'{form_key}: эскалация отклонена — {why}')
        return
    conflicts = sibling_conflicts(name, form_key, fresh, llm.get('columns') or [])
    if conflicts:
        warnings.append(
            f'{form_key}: эскалация расходится с отчётом за другой год на {len(conflicts)} '
            f'строках — возможно пересчёт, а не ошибка (проверить вручную)')
        print(f'  escalate: {len(conflicts)} rows conflict with the other year\'s report')
    fm = val_map(fresh)
    # name-based map: fresh rows that carry a wanted code (maybe assigned by name)
    nm = {}
    for it in fresh:
        for rec in [it] + (it.get('children') or []):
            if rec.get('name') and rec.get('code') in want and rec.get('values'):
                nm.setdefault(_nk(rec['name']), rec.get('values'))
    # --- quality gates: escalation may not make the form worse -------------------------
    # Values used to be overwritten unconditionally: any non-empty row the second model
    # produced won, and nothing checked that the result was BETTER than what it replaced.
    # The LLM fallback in the text branch has had such a gate for a long time (the
    # 'llm fallback passed fewer checks' branch below); escalation had none.
    #
    # What that cost, measured: of the 3 rows escalation ever changed, one was HARMFUL.
    # ТГК-14_6мес_2025, code 1250, column 0: the artifact held 11081647 and escalation
    # replaced it with 11061647 — a 20000 difference. Rule 1200 closes EXACTLY on
    # 11081647 (sum of 1210+1215+1220+1230+1240+1250+1260 = 16911114 = 1200, gap 0) and
    # is off by exactly 20000 on 11061647, so the replaced value is provably the wrong
    # one. Note where the wrong value came from: the SAME model, at the same 300 dpi,
    # reading the same page under the other provider, produced the other digit. No
    # provider is uniformly better here — on the one page of this corpus with a text
    # layer to check against, Polza fabricated numbers and PlusVibe did not, and on this
    # page it is the other way round.
    #
    # Gate 1 — support: the new value must be findable in the transcript that was sent.
    #   Escalation exists to READ the page better, not to compute or invent, so a value
    #   that cannot be pointed to is not applied. Caveat, measured: this catches the
    #   harmful change only when the sent text did not contain it (with Polza active it
    #   did not, with PlusVibe it did), so gate 1 alone is not sufficient.
    # Gate 2 — no regression: the merge is discarded entirely if it loses the closing
    #   total or leaves fewer passing checks than before. This is the gate that catches
    #   the case above — but only because rule 1200 now includes 1215. While 1215 was
    #   missing from the sum, the CORRECT value failed the rule too, so the damage was
    #   invisible to any check-count comparison. Fixing the rule is what restored the
    #   signal that makes this gate work.
    sent_nums = set(re.findall(r'\d+', re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', transcript)))
    before = copy.deepcopy(res['items'])
    was_ok = n_checks_ok(form_key, before)
    was_complete = form_is_complete(form_key, before)
    changed = 0; confirmed = 0
    unsupported = []
    for it in res['items']:
        code = it.get('code')
        targets = [it] + it.get('children', [])
        for tgt in targets:
            ccode = tgt.get('code') if tgt is not it else code
            nv = fm.get(ccode) if ccode and ccode in want else None
            if nv is None and tgt.get('name'):
                nv = nm.get(_nk(tgt['name']))
            if nv is not None and any(v is not None for v in nv):
                nv = list(nv)
                if tgt.get('values') != nv:
                    missing = [v for v in nv if v is not None
                               and re.sub(r'\D', '', str(v)) not in sent_nums]
                    if missing:
                        unsupported.append((ccode, missing))
                        continue
                    tgt['values_ocr1'] = tgt.get('values')
                    tgt['values'] = nv
                    tgt['corrected_by'] = M_ESC
                    changed += 1
                else:
                    tgt['confirmed_by'] = M_ESC
                    confirmed += 1
    print(f'  escalate: corrected {changed} rows, confirmed {confirmed}'
          + (f', NOT supported by transcript: {len(unsupported)}' if unsupported else ''))
    if unsupported:
        # the value stays as it was: an unverifiable change is not an improvement
        shown = '; '.join(f'{c}={" / ".join(str(v) for v in vs)}' for c, vs in unsupported[:4])
        warnings.append(
            f'{form_key}: эскалация предложила значения, которых нет в её же тексте '
            f'({shown}) — не применены, оставлены прежние значения')
    if changed:
        now_ok = n_checks_ok(form_key, res['items'])
        now_complete = form_is_complete(form_key, res['items'])
        if was_complete and not now_complete:
            res['items'] = before
            warnings.append(
                f'{form_key}: эскалация отклонена — потеряла {TERMINAL_CODE[form_key]} '
                f'({was_ok} проверок было, {now_ok} стало); значения возвращены')
            print(f'  escalate: REFUSED — lost {TERMINAL_CODE[form_key]}')
            changed = 0
        elif now_ok < was_ok:
            res['items'] = before
            warnings.append(
                f'{form_key}: эскалация отклонена — проверок стало меньше '
                f'({was_ok} -> {now_ok}); значения возвращены к состоянию до эскалации')
            print(f'  escalate: REFUSED — checks {was_ok} -> {now_ok}')
            changed = 0
    if changed:
        res['checks'] = [dict(form=form_key, **c) for c in run_checks(form_key, res['items'])]
        # replace this form's checks in the result
        result['checks'] = [c for c in result['checks'] if c['form'] != form_key] + res['checks']
    else:
        res['checks'] = [dict(form=form_key, **c) for c in run_checks(form_key, res['items'])
                         if False] or [c for c in result['checks'] if c['form'] == form_key]
    if res['checks'] and all(c['ok'] for c in res['checks']):
        warnings.append(f'{form_key}: fixed by escalation ({M_ESC})')
    else:
        second_opinion = 'second model agrees; document may not reconcile' if confirmed else 'unresolved'
        warnings.append(f'{form_key}: escalation did not fully reconcile ({second_opinion})')

def company_from_file(name):
    """company name from file name: 'ТГК-14_6мес_2025.pdf' -> 'ТГК-14'"""
    base = re.sub(r'_(\d+мес|год)_\d{4}\.pdf$', '', name, flags=re.I)
    return os.path.splitext(base)[0].strip()

def wanted_forms(name):
    """Form scope per file: 2025 -> balance only (scope cut); PILOT_FORMS=balance,cash_flow overrides."""
    if os.environ.get('PILOT_FORMS'):
        return {f.strip() for f in os.environ['PILOT_FORMS'].split(',') if f.strip()}
    if re.search(r'_2025\.pdf$', name, flags=re.I):
        return {'balance'}
    return set(FORMS.values())

def company_from_title(t1):
    """inn/okpo/unit from title page (name comes from filename)"""
    flat = re.sub(r'\s+', ' ', (t1 or '').replace('|', ' '))
    out = {}
    for key, pat in (('inn', r'ИНН[^0-9]{0,8}(\d{10,12})'),
                     ('okpo', r'ОКПО[^0-9]{0,8}(\d{8,10})'),
                     ('ogrn', r'ОГРН[^0-9]{0,8}(\d{13})')):
        mm = re.search(pat, flat)
        if mm: out[key] = mm.group(1)
    mu = re.search(r'(тыс\.?\s*руб|млн\.?\s*руб|руб(?:лей)?)(?![а-я])', flat, re.I)
    if mu: out['unit'] = mu.group(1)
    return out

def model_tag(model):
    """Filesystem-safe, NEVER-empty model tag for cache keys.

    'google/gemini-3.8-flash' -> 'gemini-3.8-flash'. For the real escalation model
    (`anthropic/<name>`) this returns exactly what `model.split('/')[-1]` returned, so it
    changes no existing key. It exists so that a model id with a trailing slash, or an
    empty one, can never silently produce a key that does not say which model wrote it.
    """
    for part in (str(model).split('/')[-1], str(model).split('/')[0], str(model)):
        tag = re.sub(r'[^A-Za-z0-9._-]+', '-', part).strip('-')
        if tag:
            return tag
    return 'unknown'

_FINGERPRINTS = {}

def doc_fingerprint(doc):
    """sha1 of the PDF BYTES (first 10 hex) — the identity of the file, not of its name.

    Two files can share a name (re-download, replaced file) and two names can share
    content. The cache key must follow the bytes.
    """
    path = getattr(doc, 'name', None) or ''
    if not path or not os.path.exists(path):
        return 'nofile'
    if path not in _FINGERPRINTS:
        h = hashlib.sha1()
        with open(path, 'rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b''):
                h.update(chunk)
        _FINGERPRINTS[path] = h.hexdigest()[:10]
    return _FINGERPRINTS[path]

def _doc_stem(doc):
    return os.path.splitext(os.path.basename(getattr(doc, 'name', '') or ''))[0]

def _provider_infix(profile=None):
    """The provider's fragment of a cache name, with a leading underscore — or ''.

    Empty for the legacy provider, so its existing cache names keep their meaning and
    switching provider costs no re-transcription. One helper, because this fragment is
    used in more than one place and the two uses drifting apart is how defect 4.1 looked.
    """
    suffix = (profile or ACTIVE_PROFILE).cache_suffix()
    return f'_{suffix}' if suffix else ''

def page_cache_path(doc, name, p, dpi, model, profile=None):
    """Disk path of one page transcript.

    The key carries four independent identity facts: document stem, page, dpi, model —
    plus the PDF fingerprint, so a replaced file cannot inherit the old transcript.
    Split out from transcribe_cached so the key can be tested without paying for a call.
    Raises when `name` does not identify the open PDF: defect 4.1 came from a caller
    passing name='x', which made every document share one key and handed Корпсан's
    balance to ТГК-14 and Органик парк.

    The provider is part of the key too: two sites serving a model under the same name
    must not share a transcript. Polza's keys stay byte-identical — its cache suffix is
    empty — so switching provider costs no re-transcription. PlusVibe variants differ by
    an address suffix (`:network`), which `model_tag` sanitizes to '-', so their keys
    differ automatically and need no separate field.
    """
    stem = os.path.splitext(name)[0]
    if not stem or stem != _doc_stem(doc):
        raise ValueError(
            f'cache key would not identify the document: name={name!r} '
            f'but the open PDF is {getattr(doc, "name", None)!r}')
    prof = profile or ACTIVE_PROFILE
    prov = _provider_infix(prof)
    return os.path.join(PAGESDIR,
                        f'{stem}_p{p}_{dpi}_{model_tag(model)}{prov}_{doc_fingerprint(doc)}.md')

def transcribe_cached(doc, p, name, dpi=200, model=M_MAIN):
    """transcribe one page with disk cache (crash-resilient, free reruns)"""
    cache = page_cache_path(doc, name, p, dpi, model)
    if os.path.exists(cache):
        return open(cache, encoding='utf-8').read()
    msg = [img_message(render_png(doc[p - 1], dpi),
                       TRANSCRIBE_PROMPT + f' (страница {p} файла)')]
    txt, fin = chat(msg, model, max_tokens=16000)
    if fin == 'length':
        txt2, _ = chat([img_message(render_png(doc[p - 1], min(dpi + 100, 300)),
                        TRANSCRIBE_PROMPT + ' Продолжи ровно с места обрыва, без повторов.')],
                       model, max_tokens=16000)
        txt = txt + txt2
    if fin == 'content_filter':
        # Провайдер обрезал ответ своим фильтром (видели на балансе ИПС: строка
        # оборвана на «| Проценты по краткосрочным займам | 151»). Такой ответ
        # нельзя класть в кэш: он неполон, а кэш сделал бы неполноту вечной и
        # бесплатной для повторного чтения. Повторяем один раз с повышенным
        # разрешением — обрезка часто зависит от того, как модель разметила
        # страницу, и на другом рендере не повторяется. Если и повтор срезан,
        # отдаём то, что есть, с предупреждением: пусть решает эскалация формы,
        # а не исключение посреди прогона.
        print(f'  [cache] страница {p}: ответ срезан фильтром содержимого — повтор на '
              f'{min(dpi + 100, 300)}dpi, в кэш пока не кладу')
        txt2, fin2 = chat([img_message(render_png(doc[p - 1], min(dpi + 100, 300)),
                          TRANSCRIBE_PROMPT + f' (страница {p} файла)')],
                         model, max_tokens=16000)
        if fin2 != 'content_filter':
            txt, fin = txt2, fin2
            print(f'  [cache] страница {p}: повтор удался (finish={fin2})')
        else:
            print(f'  [cache] страница {p}: повтор тоже срезан фильтром — отдаю '
                  f'неполный текст, форму придётся эскалировать')
            return txt
    open(cache, 'w', encoding='utf-8').write(txt)
    return txt

def cached_llm(tag, fn):
    """cache LLM JSON results on disk; tag must be unique per call.

    Everything cached here was produced by a model — escalation, page detection,
    form structuring — so the provider belongs in the name for the same reason it
    belongs in a page transcript's: two sites serving one model name must not share
    an artifact, or one provider's answer silently becomes another's. Polza's infix
    is empty, so its existing files keep their names byte for byte.
    """
    path = os.path.join(PAGESDIR, f'_llm_{tag}{_provider_infix()}.json')
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))
    obj = fn()
    json.dump(obj, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
    return obj

def detect_pages(doc, cand, npages, warnings):
    """Stage 1: label every candidate page with a category, cheap model at 120 dpi.

    Extracted from scan_pipeline so that the paid detection pass can be run, compared and
    re-run on its own — detection is the cheap stage (0.22 ₽ for the whole 41-document
    pilot), and the only way to measure a change to DETECT_PROMPT is to call exactly this
    function and diff the labels it returns.
    """
    msgs = [{'role': 'user', 'content': [{'type': 'text', 'text': DETECT_PROMPT}]}]
    for i in cand:
        msgs[0]['content'].extend(img_parts(render_png(doc[i - 1], 120), f'СТРАНИЦА {i}'))
    print(f'  detection: {len(cand)} candidate pages sent as images')
    if len(cand) <= 10:
        txt, _ = chat(msgs, M_DETECT, temperature=0, max_tokens=4000)
        try:
            pm = extract_json(txt).get('pages', [])
        except ValueError:
            pm = salvage_pages_map(txt, npages)
        return pm or salvage_pages_map(txt, npages)
    # chunked detection for big candidate sets: classify each page group separately;
    # polza rejects requests whose images exceed ~30MB total, so chunks are small and a
    # failed chunk is retried in halves
    pages_map = []
    CH = 8
    def _detect_group(group):
        cm = [{'role': 'user', 'content': [
            {'type': 'text', 'text': DETECT_PROMPT + f' (Страницы {group[0]}-{group[-1]} из {npages})'}]}]
        for j in group:
            cm[0]['content'].extend(img_parts(render_png(doc[j - 1], 120), f'СТРАНИЦА {j}'))
        try:
            # 4000, not 1200: the group path used to ask for less than the single-message
            # path above, and a reasoning model spends part of the limit on its own
            # reasoning before emitting any JSON. At 1200 the limit ran out before the
            # answer started: 16% of calls came back as HTTP 502 «весь заданный вами
            # max_tokens ушёл на внутренние рассуждения» (25 calls, 4 failures).
            # At 4000 the same 25 calls all returned text. 4000 is already the value
            # chosen for the single-message path, so this makes the two agree.
            txt, _ = chat(cm, M_DETECT, temperature=0, max_tokens=4000)
        except Exception as e:
            if len(group) > 2:
                mid = len(group) // 2
                _detect_group(group[:mid])
                _detect_group(group[mid:])
            else:
                warnings.append(f'detection: pages {group} skipped: {e}')
            return
        pm = salvage_pages_map(txt, npages)
        if not pm:
            try:
                pm = extract_json(txt).get('pages', [])
            except ValueError:
                pm = []
        pages_map.extend(pm)
    for lo in range(0, len(cand), CH):
        _detect_group(cand[lo:lo + CH])
    return pages_map

def scan_pipeline(doc, name, only_pages=None):
    warnings, transcripts = [], {}
    npages = len(doc)
    cand = only_pages or list(range(1, npages + 1))
    # stage 1: detection, cheap model, 120 dpi — all pages as content parts of ONE message
    try:
        pages_map = cached_llm(f'{os.path.splitext(name)[0]}_detect_{DETECT_PROMPT_VERSION}',
                               lambda: detect_pages(doc, cand, npages, warnings))
    except Exception as e:
        warnings.append(f'detection failed: {e}')
        pages_map = []
    form_pages = {}
    for p in pages_map:
        f = p.get('form')
        if f in FORM_LABELS:
            form_pages.setdefault(f, []).append(p.get('page'))
    # Notes and the auditor's report are separate documents, not forms: they used to be
    # labelled with a form, so their pages entered transcript_pages and escalation then
    # re-read them at 300 dpi as if they were part of the balance. Measured: 13 documents
    # contaminated, 18 notes pages, and for КЛВЗ Кристалл_6мес_2025 four of the eight pages
    # escalation read were notes (22, 23, 25, 26) while the balance sat on pages 1-2.
    # They are dropped from the run now, but the page numbers are kept in the artifact as a
    # hook: the auditor's report is wanted later, and it precedes the balance in annual
    # reporting, so "page 1 is the balance" must never be assumed.
    doc_result['_extra_pages'] = {
        'notes': sorted({p.get('page') for p in pages_map if p.get('form') == 'notes'}),
        'audit': sorted({p.get('page') for p in pages_map if p.get('form') == 'audit'}),
    }
    print('  detected form pages:', form_pages)
    if doc_result['_extra_pages']['notes'] or doc_result['_extra_pages']['audit']:
        print('  detected non-form text pages: notes=%s audit=%s'
              % (doc_result['_extra_pages']['notes'], doc_result['_extra_pages']['audit']))
    want = wanted_forms(name)
    if want:
        form_pages = {k: v for k, v in form_pages.items() if k in want}
        print(f'  forms wanted: {sorted(want)} -> kept: {sorted(form_pages)}')
    # stage 2: transcription, main model, 200 dpi — parallel workers, disk-cached per page
    # The title page is NOT a form page — detection now labels it `other` — but it carries
    # inn/okpo/unit, which were previously picked up only because page 1 happened to be
    # labelled with a form and so became `balance_p1`. Without this, company_from_title
    # would silently lose them (measured on the new labels: Артген (ИСКЧ)_6мес_2025 lost
    # ОКПО 71328785 and the unit «тыс. руб»). Transcribe page 1 on its own under a stable
    # key; when page 1 is also a form page this is a cache hit and costs nothing.
    title_pages = [1] if npages >= 1 else []
    from concurrent.futures import ThreadPoolExecutor
    todo = sorted({p for plist in form_pages.values() for p in plist
                   if isinstance(p, int) and 1 <= p <= npages} | set(title_pages))
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda p: transcribe_cached(doc, p, name, dpi=200, model=M_MAIN), todo))
    for p in title_pages:
        transcripts[f'title_p{p}'] = transcribe_cached(doc, p, name, dpi=200, model=M_MAIN)
    for key, plist in form_pages.items():
        parts = []
        for p in plist:
            if not isinstance(p, int) or p < 1 or p > npages: continue
            txt = transcribe_cached(doc, p, name, dpi=200, model=M_MAIN)
            parts.append(f'=== СТРАНИЦА {p} ===\n{txt}')
            transcripts[f'{key}_p{p}'] = txt
        if parts:
            # stage 3: structure (+ split-in-half retry for truncated/broken output)
            full = '\n\n'.join(parts)
            def _struct(): return llm_structure_form(full, key)[0]
            try:
                structured = cached_llm(f'{os.path.splitext(name)[0]}_struct_{key}', _struct)
            except Exception as e:
                warnings.append(f'{key}: whole-form structure failed ({e}); trying split')
                structured = None
            if structured is None and len(parts) > 1:
                mid = len(parts) // 2
                def _s1(): return llm_structure_form('\n\n'.join(parts[:mid]), key)[0]
                def _s2(): return llm_structure_form('\n\n'.join(parts[mid:]), key)[0]
                try:
                    a = cached_llm(f'{os.path.splitext(name)[0]}_struct_{key}_A', _s1)
                    b = cached_llm(f'{os.path.splitext(name)[0]}_struct_{key}_B', _s2)
                    a.setdefault('items', []).extend(b.get('items', []))
                    structured = a
                    warnings.append(f'{key}: structured in 2 parts')
                except Exception as e:
                    warnings.append(f'{key}: split structuring failed: {e}')
                    structured = None
            if structured is not None:
                doc_result[key] = {'transcript_pages': plist, 'llm': structured}
    return warnings, transcripts

# ---------------------------------------------------------------- main
doc_result = {}

def collect_scan_results(doc, name, transcripts, result):
    """doc_result (global, filled by scan_pipeline) -> result dict + checks + escalation"""
    result['source']['ocr_model'] = M_MAIN
    # Происхождение: через месяц нужно понимать, каким поставщиком сделана
    # транскрипция — цены и качество у площадок разные, а имя модели совпадает.
    result['source']['provider'] = ACTIVE_PROFILE.name
    # page 1 of a scan holds the title page: inn/okpo/unit (name from filename).
    # `title_p1` is the fallback for when detection labelled page 1 as a non-form page.
    rq = company_from_title(transcripts.get('balance_p1') or transcripts.get('title_p1') or '')
    result['company'].update({k: rq[k] for k in ('inn', 'okpo') if rq.get(k)})
    if rq.get('unit'): result['unit']['label'] = rq['unit']
    for key in ('balance', 'income_statement', 'cash_flow'):
        d = doc_result.get(key)
        if not d: continue
        items = _normalize_llm(d['llm'], key)
        result[key] = {'form': [k for k, v in FORMS.items() if v == key][0],
                       'columns': d['llm'].get('columns', []),
                       'items': items, 'transcript_pages': d['transcript_pages']}
        result['checks'] += [dict(form=key, **c) for c in run_checks(key, items)]
    # Hook for later: pages detection labelled as notes / auditor's report. They are not
    # read now (they are text documents, not forms, and were previously polluting both the
    # forms and escalation), but the page numbers are recorded so the next stage can pick
    # up the auditor's report — which is the first thing wanted — without re-detecting.
    non_form = doc_result.get('_extra_pages') or {}
    non_form = {k: v for k, v in non_form.items() if v}
    if non_form:
        result['source']['non_form_pages'] = non_form
        result['warnings'].append(
            'страницы, не являющиеся формами, пропущены (задел на будущее): '
            + ', '.join(f'{k} — стр. {v}' for k, v in sorted(non_form.items())))
    # drop 'empty' forms: structuring returned nothing usable (wrong-page garbage)
    for key in ('balance', 'income_statement', 'cash_flow'):
        d = result.get(key)
        if not d: continue
        nvals = _values_count(d['items'])
        top = [it for it in d['items'] if it.get('code') in KNOWN_TOP]
        if nvals < 5 or not top:
            result['warnings'].append(
                f'{key}: structuring produced no usable table (nvalues={nvals}, canon_top={len(top)}) -> dropped')
            result[key] = None
            result['checks'] = [c for c in result['checks'] if c['form'] != key]
    # completeness check (decision 15) for the scan branch too: the passive page of
    # a balance may simply not have been detected as a form page (defect 4.2)
    for key in ('balance', 'income_statement', 'cash_flow'):
        d = result.get(key)
        if not d or form_is_complete(key, d['items']):
            continue
        used = list(d.get('transcript_pages') or [])
        extra = extra_form_pages(doc, used)
        if not extra:
            continue
        print(f'  {key}: no {TERMINAL_CODE[key]} -> trying pages {extra}')
        try:
            pages_all = used + extra
            parts = [f'=== СТРАНИЦА {p} ===\n{transcribe_cached(doc, p, name, dpi=200, model=M_MAIN)}'
                     for p in pages_all]
            tag = f"{os.path.splitext(name)[0]}_tstruct_{key}_p{'_'.join(map(str, pages_all))}"
            llm = cached_llm(tag, lambda: llm_structure_form('\n\n'.join(parts), key)[0])
            items2 = _normalize_llm(llm, key)
        except Exception as e:
            result['warnings'].append(f'{key}: recovering pages {extra} failed: {e}')
            continue
        if form_is_complete(key, items2):
            d['items'] = items2
            if llm.get('columns'): d['columns'] = llm['columns']
            d['structured_by'] = 'llm_completion'
            d['transcript_pages'] = pages_all
            result['source'].setdefault('pages_used', []).extend(extra)
            result['checks'] = [c for c in result['checks'] if c['form'] != key] + \
                               [dict(form=key, **c) for c in run_checks(key, items2)]
            result['warnings'].append(
                f'{key}: form was cut off; pages {extra} recovered {TERMINAL_CODE[key]}')
        else:
            result['warnings'].append(
                f'{key}: pages {extra} did not yield {TERMINAL_CODE[key]}')
    # escalation: failed forms -> re-OCR problem pages at 300 dpi with M_ESC
    for key in ('balance', 'income_statement', 'cash_flow'):
        if result.get(key) and not all(c['ok'] for c in result['checks'] if c['form'] == key):
            escalate_failed_form(doc, key, result, result['warnings'], name=name)
    for k, t in transcripts.items():
        # This is a diagnostic dump of the transcripts the pipeline worked from, not the
        # paid cache — nothing reads it back. It still must name the provider: the same
        # file name used to receive Polza's transcript in one run and PlusVibe's in the
        # next, which is how defect 4.1 looked before it was found.
        open(os.path.join(PAGESDIR, f'{os.path.splitext(name)[0]}_{k}{_provider_infix()}.md'),
             'w', encoding='utf-8').write(t)

def _garbled_page(pg):
    """page has an image and >=600 chars of 'text' dominated by Latin letters ->
    broken OCR text layer (real RSBU text is Cyrillic); treat page as scan"""
    t = pg.get_text()
    if not pg.get_images() or len(t) < 600:
        return False
    a = [c for c in t if c.isalpha()]
    if len(a) < 200:
        return False
    return sum(1 for c in a if ord(c) < 128) / len(a) > 0.5

def process(path):
    name = os.path.basename(path)
    print(f'== {name}')
    doc = pymupdf.open(path)
    chars = sum(len(pg.get_text().strip()) for pg in doc)
    has_text = chars > 200
    # broken OCR layer: many image pages whose 'text' is Latin garbage -> scan branch
    garbled = [p for p in range(1, len(doc) + 1) if _garbled_page(doc[p - 1])]
    if len(garbled) >= max(2, len(doc) // 4):
        has_text = False
    result = {'schema_version': '1.1',
              'source': {'file': name, 'pages_total': len(doc), 'text_layer': has_text,
                         'provider': ACTIVE_PROFILE.name},
              'company': {'name': company_from_file(name)}, 'period': {}, 'unit': {},
              'balance': None, 'income_statement': None, 'cash_flow': None,
              'checks': [], 'warnings': []}
    if garbled and not has_text:
        result['warnings'].append(
            f'broken OCR text layer on {len(garbled)}/{len(doc)} pages -> scan branch')
    want = wanted_forms(name)
    print(f'  forms wanted: {sorted(want) if want else "all"}')
    # title page info (text branch only; scan branch gets it from LLM structuring)
    if has_text:
        rq = company_from_title(doc[0].get_text())
        result['company'].update({k: rq[k] for k in ('inn', 'okpo') if rq.get(k)})
        if rq.get('unit'): result['unit']['label'] = rq['unit']
        fp = find_form_pages(doc)
        if want: fp = {k: v for k, v in fp.items() if k in want}
        print('  text-branch form pages:', fp)
        form_pages = {k: list(v) for k, v in fp.items()}
        for key, plist in fp.items():
            columns, items, warns = structure_text_form(doc, plist, key)
            result[key] = {'form': [k for k, v in FORMS.items() if v == key][0],
                           'columns': columns, 'items': items}
            result['warnings'] += [f'{key}: {w}' for w in warns]
            result['source'].setdefault('pages_used', []).extend(plist)
        # completeness check (decision 15): a form that stops before its closing
        # total row was cut off — its continuation is on the next page, which may
        # be image-only and therefore invisible to the text branch (defect 4.2)
        for key in list(fp):
            if form_is_complete(key, result[key]['items']):
                continue
            extra = extra_form_pages(doc, form_pages[key])
            if not extra:
                continue
            print(f'  {key}: no {TERMINAL_CODE[key]} -> trying image-only pages {extra}')
            try:
                parts = [f'=== PAGE {p} ===\n{doc[p-1].get_text()}' for p in form_pages[key]]
                parts += [f'=== PAGE {p} ===\n{transcribe_cached(doc, p, name, dpi=200, model=M_MAIN)}'
                          for p in extra]
                pages_all = form_pages[key] + extra
                tag = f"{os.path.splitext(name)[0]}_tstruct_{key}_p{'_'.join(map(str, pages_all))}"
                llm = cached_llm(tag, lambda: llm_structure_form('\n\n'.join(parts), key)[0])
                items2 = _normalize_llm(llm, key)
            except Exception as e:
                result['warnings'].append(f'{key}: recovering pages {extra} failed: {e}')
                continue
            if form_is_complete(key, items2):
                result[key]['items'] = items2
                if llm.get('columns'): result[key]['columns'] = llm['columns']
                result[key]['structured_by'] = 'llm_completion'
                form_pages[key] = pages_all
                result['source'].setdefault('pages_used', []).extend(extra)
                result['warnings'].append(
                    f'{key}: form was cut off; pages {extra} recovered {TERMINAL_CODE[key]}')
            else:
                result['warnings'].append(
                    f'{key}: pages {extra} did not yield {TERMINAL_CODE[key]}')
        # if checks fail -> LLM structuring fallback (escalation rule 1)
        for key in list(fp):
            chks = run_checks(key, result[key]['items'])
            result[key]['transcript_pages'] = form_pages[key]
            if not all(c['ok'] for c in chks):
                print(f'  {key}: rule-parse checks FAILED -> LLM fallback')
                txt = '\n\n'.join(f'=== PAGE {p} ===\n{doc[p-1].get_text()}' for p in form_pages[key])
                tag = f"{os.path.splitext(name)[0]}_tstruct_{key}_p{'_'.join(map(str, form_pages[key]))}"
                try:
                    llm = cached_llm(tag, lambda: llm_structure_form(txt, key)[0])
                    items = _normalize_llm(llm, key)
                    was, now = n_checks_ok(key, result[key]['items']), n_checks_ok(key, items)
                    if form_is_complete(key, result[key]['items']) and not form_is_complete(key, items):
                        # Проект 111_6мес_2025 lost its whole passive side this way:
                        # a complete rule parse was replaced by 5 rows ending at 1150
                        result['warnings'].append(
                            f'{key}: llm fallback lost {TERMINAL_CODE[key]} -> kept rule parse')
                    elif now < was:
                        result['warnings'].append(
                            f'{key}: llm fallback passed fewer checks ({now} < {was}) -> kept rule parse')
                    else:
                        result[key]['items'] = items
                        if llm.get('columns'): result[key]['columns'] = llm['columns']
                        result[key]['structured_by'] = 'llm_fallback'
                except Exception as e:
                    result['warnings'].append(f'{key}: llm fallback failed: {e}')
            # sync this form's checks; balance still failing -> 300dpi escalation
            chks2 = [dict(form=key, **c) for c in run_checks(key, result[key]['items'])]
            result['checks'] = [c for c in result['checks'] if c['form'] != key] + chks2
            if key == 'balance' and not all(c['ok'] for c in chks2):
                escalate_failed_form(doc, key, result, result['warnings'], name=name)
        if not fp:
            # text layer present but no target forms in text. Two cases:
            #  a) hybrid: forms are SCANS (image-only pages) -> cheap detection over
            #     image-only pages only, then scan branch on the detected pages
            #  b) notes-only: no image pages -> one cached LLM pass over table-like
            #     text pages, else no_forms (never burn vision OCR on notes-only PDF)
            img_pages = [p for p in range(1, len(doc)+1)
                         if doc[p-1].get_images(full=True) and len(doc[p-1].get_text().strip()) < 600]
            if img_pages:
                result['warnings'].append(f'text has no forms; {len(img_pages)} image-only pages -> scan detection')
                doc_result.clear()
                warn, transcripts = scan_pipeline(doc, name, only_pages=img_pages)
                result['warnings'] += warn
                collect_scan_results(doc, name, transcripts, result)
            else:
                tpages = [p for p in range(1, len(doc)+1)
                          if 'Наименование показателя' in doc[p-1].get_text()]
                if tpages:
                    print(f'  text LLM fallback on pages {tpages}')
                    txt = '\n\n'.join(f'=== СТРАНИЦА {p} ===\n{doc[p-1].get_text()}' for p in tpages)
                    def _txt_fb(): return llm_structure_form(txt, 'balance')[0]
                    llm = cached_llm(f'{os.path.splitext(name)[0]}_txtfb', _txt_fb)
                    items = _normalize_llm(llm, 'balance')
                    chks = run_checks('balance', items)
                    if any(v is not None for v in (val_map(items).get('1600') or [])):
                        result['balance'] = {'form': '0710001', 'columns': llm.get('columns', []),
                                             'items': items, 'structured_by': 'llm_text_fallback'}
                        result['checks'] += [dict(form='balance', **c) for c in chks]
                    else:
                        result['warnings'].append('text LLM fallback: no 1600 in LLM answer')
                if not result.get('balance'):
                    result['warnings'].append('no target forms found in document (notes-only PDF?)')
                    result['status'] = 'no_forms'
    else:
        doc_result.clear()
        warn, transcripts = scan_pipeline(doc, name)
        result['warnings'] += warn
        collect_scan_results(doc, name, transcripts, result)
    doc.close()
    per_form_ok = {}
    for c in result['checks']:
        per_form_ok.setdefault(c['form'], []).append(bool(c.get('ok')))
    if result['checks'] and all(all(v) for v in per_form_ok.values()):
        result['status'] = 'ok'
    elif result['checks']:
        result['status'] = 'needs_review'
    elif not any(result.get(k) for k in FORMS):
        result['warnings'].append('no target forms found in document')
        result['status'] = 'no_forms'
    else:
        result['status'] = 'incomplete'
    out = os.path.join(OUTDIR, os.path.splitext(name)[0] + '.json')
    json.dump(result, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'  -> {out} status={result["status"]}')
    return result

if __name__ == '__main__':
    os.makedirs(OUTDIR, exist_ok=True); os.makedirs(PAGESDIR, exist_ok=True)
    targets = sys.argv[1:] or ['Рекорд трейд_6мес_2026.pdf', 'Корпсан_6мес_2026.pdf']
    results = []
    for t in targets:
        p = t if os.path.isabs(t) else os.path.join(DOWNLOADS, t)
        try:
            results.append(process(p))
        except Exception as e:
            import traceback; traceback.print_exc()
            results.append({'file': t, 'status': 'failed', 'error': str(e)})
    manifest = {'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
                'provider': ACTIVE_PROFILE.name,
                'usage': USAGE,
                'usage_note': ('cost_rub — фактическая стоимость прогона: из заголовка '
                               'ответа поставщика, если он его сообщает, иначе по таблице '
                               'цен профиля; calls — число сделанных вызовов'),
                'files': [{'file': r.get('file') or r.get('source', {}).get('file'),
                           'status': r.get('status'),
                           'provider': r.get('source', {}).get('provider'),
                           'warnings': r.get('warnings', [])[:5],
                           'error': r.get('error')} for r in results]}
    json.dump(manifest, open(os.path.join(OUTDIR, '_manifest.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f"итого: вызовов {USAGE['calls']}, токенов {USAGE['prompt']}/{USAGE['completion']}, "
          f"стоимость {USAGE['cost_rub']:.2f} RUB (поставщик {ACTIVE_PROFILE.name})")
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
