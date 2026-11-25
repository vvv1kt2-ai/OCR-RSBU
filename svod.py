# -*- coding: utf-8 -*-
"""Свод JSON-результатов извлечения РСБУ в таблицу по форме sum.csv.

Соглашения (согласованы с пользователем + конвенции pipeline.py):
- Баланс: колонка «На 30 июня N» берётся из файла своего года.
- ОФР и ОДДС: обе колонки (2025 и 2026) берутся ТОЛЬКО из файла-2026.
- Код извлекается как ПОСЛЕДНИЙ верхнеуровневый item с этим кодом (val_map из pipeline.py).
- Расходные/платёжные строки в JSON хранятся отрицательными; проверки знако-независимые.
- Аренда/лизинг (пассив) по колонке «30 июня»: долгосрочные строки -> 1450,
  краткосрочные -> 1550, только если лежат ВНЕ самих кодов 1450/1550.
- Подозрение на дубль -> складывается, ячейка помечается.
- 2330 в своде положительным; JSON не меняется. Нет файла года -> «нет». «МСФО»-строки пустые.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, 'D:/models/pylibs')

EXTRACTED = Path('D:/models/extracted')
DEBUG_PATH = Path('D:/models/tmp/svod_debug.json')

BAL_CODES = ('1510', '1550', '1410', '1450', '1250', '1300')
IS_CODES = ('2110', '2300', '2330', '2320')
CF_CODES = ('4100', '4110')

EMITTERS = [
    'ТГК-14', 'КИФА', 'Проект 111', 'Афанасий', 'Омега', 'Байсэл',
    'Бианка премиум', 'Сибсульфур', 'Простая еда', 'Славянск ЭКО',
    'НовосибирскАвтодор', 'Моторные технологии', 'Эфферон', 'Эфферон МСФО',
    'Нижегородец Восток', 'Финэква', 'Органик парк', 'ИПС',
    'Артген (ИСКЧ) МСФО', 'Артген (ИСКЧ)', 'Смартфакт', 'КЛВЗ Кристалл',
]
ORPHANS = ['Корпсан', 'Рекорд трейд']

TOL = 2

LONG_RENT_RE = re.compile(r'долгосрочн\w*.*(?:аренд|лизинг)', re.I)
SHORT_RENT_RE = re.compile(r'краткосрочн\w*.*(?:аренд|лизинг)', re.I)
LEASE_RE = re.compile(
    r'обязательств\w* по аренде|расчеты по обязательствам по аренде|'
    r'арендные обязательства|задолженность по арендным обязательствам', re.I)
PARENT_SHORT_RE = re.compile(r'краткосрочн|кредиторская', re.I)
PARENT_LONG_RE = re.compile(r'долгосрочн|прочие обязательства', re.I)
AVANS_RE = re.compile(r'аванс', re.I)


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def walk(items):
    for it in items or []:
        yield it
        yield from walk(it.get('children'))


def mark_chains(form):
    """Проставить _chain (коды родителей) для каждого item, включая верхний уровень."""
    def mark(items, parent_codes):
        for it in items:
            it['_chain'] = list(parent_codes)
            mark(it.get('children') or [], parent_codes + [it.get('code') or ''])
    mark(form.get('items') or [], [])


def get_val(form, code, idx):
    """Значение кода в колонке idx; из ПОСЛЕДНЕГО верхнеуровневого item с кодом."""
    if form is None or idx is None:
        return None
    items = [it for it in (form.get('items') or []) if it.get('code') == code]
    if not items:
        return None
    v = items[-1].get('values') or []
    return v[idx] if idx < len(v) else None


def year_pattern(year):
    """Регулярка года, устойчивая к пробелу ВНУТРИ числа.

    Транскрипция иногда отдаёт «За 1 полугод 20 26 г.» — пробел внутри года. Поиск
    непрерывной подстроки '2026' такую колонку не находит, и значение молча пропадает:
    измерено на `ИПС_6мес_2026` (ОДДС: «20 26 г.» / «20 25 г.») — в своде пустели 4 клетки
    ОДДС, хотя в артефакте числа есть, и в эталоне они тоже есть.
    """
    return re.compile(r'\s*'.join(re.escape(d) for d in str(year)))


def col_index_balance(form, year):
    if not form:
        return None
    iso = f'{year}-06-30'
    pat = re.compile(r'30\s*июн\w*\s*' + year_pattern(year).pattern, re.I)
    for i, c in enumerate(form.get('columns') or []):
        cs = str(c)
        if cs == iso or pat.search(cs):
            return i
    return None


def col_index_flow(form, year):
    if not form:
        return None
    pat = year_pattern(year)
    for i, c in enumerate(form.get('columns') or []):
        if pat.search(str(c)):
            return i
    return None


def flow_columns(form, year, form_ru):
    """(idx_cur, idx_prev, warning) — колонки ОФР/ОДДС и страж «год колонки не доказан».

    Единственная копия правила. Раньше условие и текст предупреждения были продублированы
    дословно в svod.py и svod_build.py, и правка в одном месте не доезжала до другого —
    ровно та причина, по которой «свои копии правил» в этом проекте уже давали расхождение.

    Колонка СВОЕГО года обязана найтись. Если её нет, заголовки колонок этой формы не
    называют год документа, а значит не доказана и колонка прошлого года: поставить туда
    число — значит выдать числа 2026 года за 2025. Измерено на ОДДС трёх документов
    (Бианка премиум, Унител, Урожай): форма получала заголовок ЧУЖОЙ формы («На 30 июня
    2025 г.» / «На 31 декабря 2025 г.»), и свод молча писал 2026 год в колонку 2025, а 2026
    оставлял пустым — ошибка выглядела как данные. Пустая клетка плюс запись в аудите
    честнее неверного года.

    warning = None означает «колонки найдены» (или формы нет вовсе — тогда читать нечего).
    """
    if not form:
        return None, None, None
    idx_cur = col_index_flow(form, year)
    idx_prev = col_index_flow(form, year - 1)
    if idx_cur is None:
        return None, None, (f'ВНИМАНИЕ: колонки {form_ru} не называют {year} год '
                            f'(columns={form.get("columns")}) — значения {form_ru} не взяты: '
                            f'год колонки не доказан')
    return idx_cur, idx_prev, None


def check_balance(d):
    """Правила баланса (как в pipeline.run_checks, знаки натуральные)."""
    fails = []
    if not d:
        return fails
    n = max((len(it.get('values') or []) for it in d.get('items') or []), default=0)

    def S(code, c):
        return get_val(d, code, c)
    def nz(*xs):
        return sum(x for x in xs if x is not None)
    def has(*xs):
        return any(x is not None for x in xs)
    def eq(a, b):
        return a is not None and b is not None and abs(a - b) <= TOL
    rules = [
        ('1600 == 1700', lambda c: eq(S('1600', c), S('1700', c)) if has(S('1600', c)) else None),
        ('1100 == 1110+1120+1130+1140+1150+1160+1170+1180+1190',
         lambda c: eq(S('1100', c), nz(*[S(k, c) for k in ('1110','1120','1130','1140','1150','1160','1170','1180','1190')])) if has(S('1100', c)) else None),
        ('1200 == 1210+1215+1220+1230+1240+1250+1260',
         lambda c: eq(S('1200', c), nz(*[S(k, c) for k in ('1210','1215','1220','1230','1240','1250','1260')])) if has(S('1200', c)) else None),
        ('1300+1400+1500 == 1700',
         lambda c: eq(nz(S('1300', c), S('1400', c), S('1500', c)), S('1700', c)) if has(S('1700', c)) else None),
    ]
    for name, fn in rules:
        for c in range(n):
            try:
                r = fn(c)
            except Exception:
                r = None
            if r is False:
                fails.append(f'{name} [кол.{c}]')
    return fails


def check_is(d):
    """ОФР: знако-независимые проверки (как в pipeline.py), плюс 2300-цепочка."""
    fails = []
    if not d:
        return fails
    n = max((len(it.get('values') or []) for it in d.get('items') or []), default=0)

    def S(code, c):
        return get_val(d, code, c)
    def has(*xs):
        return any(x is not None for x in xs)
    def eq_pm(a, e):
        return a is not None and e is not None and (abs(a - e) <= TOL or abs(a + e) <= TOL)
    rules = [
        ('2100 == 2110-2120',
         lambda c: eq_pm(S('2100', c), (S('2110', c) or 0) - abs(S('2120', c) or 0))
         if has(S('2110', c), S('2120', c), S('2100', c)) else None),
        ('2200 == 2100-2210-2220',
         lambda c: eq_pm(S('2200', c), (S('2100', c) or 0) - abs(S('2210', c) or 0) - abs(S('2220', c) or 0))
         if has(S('2100', c), S('2200', c)) else None),
        ('2300 == 2200+2310+2320-2330+2340-2350',
         lambda c: eq_pm(S('2300', c),
                         (S('2200', c) or 0) + (S('2310', c) or 0) + (S('2320', c) or 0)
                         - abs(S('2330', c) or 0) + (S('2340', c) or 0) - abs(S('2350', c) or 0))
         if has(S('2200', c), S('2300', c)) else None),
        ('2400 == 2300-2410±2421∓2430±2450-2460',
         lambda c: (eq_pm(S('2400', c),
                          (S('2300', c) or 0) - (S('2410', c) or 0) + (S('2421', c) or 0)
                          - (S('2430', c) or 0) + (S('2450', c) or 0) - (S('2460', c) or 0))
                    or eq_pm(S('2400', c),
                          (S('2300', c) or 0) + (S('2410', c) or 0) - (S('2421', c) or 0)
                          + (S('2430', c) or 0) - (S('2450', c) or 0) + (S('2460', c) or 0)))
         if has(S('2300', c), S('2400', c)) and any(S(k, c) is not None for k in ('2410','2421','2430','2450','2460')) else None),
    ]
    for name, fn in rules:
        for c in range(n):
            try:
                r = fn(c)
            except Exception:
                r = None
            if r is False:
                fails.append(f'{name} [кол.{c}]')
    return fails


def check_cf(d):
    """ОДДС: 4100/4200/4300 (платежи отрицательными), 4400, 4500 (как в pipeline + сальдо потоков)."""
    fails = []
    if not d:
        return fails
    n = max((len(it.get('values') or []) for it in d.get('items') or []), default=0)

    def S(code, c):
        return get_val(d, code, c)
    def has(*xs):
        return any(x is not None for x in xs)
    def eq(a, b):
        return a is not None and b is not None and abs(a - b) <= TOL
    def eq_pm(a, e):
        return a is not None and e is not None and (abs(a - e) <= TOL or abs(a + e) <= TOL)
    # Правило применяется только если ВСЕ его участники есть в форме. Раньше условием было
    # «есть хотя бы один», и отсутствующие слагаемые подставлялись нулём: на форме, где
    # прочитан только 4100 (состав данных 19.11.2026 — из ОДДС нужен один код), правило
    # `4100 == 4110-4120` сравнивало сумму с нулём и объявляло провал при верных данных.
    # Замер: «Кокс_9мес_2026», «Рубеж_9мес_2025», «Энерготехсервис_9мес_2025» — по два
    # ложных провала на документ.
    def all_have(*codes):
        return all(S(code, c) is not None for code in codes)
    rules = [
        ('4100 == 4110-4120',
         lambda c: eq_pm(S('4100', c), (S('4110', c) or 0) - abs(S('4120', c) or 0))
         if all_have('4110', '4120', '4100') else None),
        ('4200 == 4210-4220',
         lambda c: eq_pm(S('4200', c), (S('4210', c) or 0) - abs(S('4220', c) or 0))
         if all_have('4210', '4220', '4200') else None),
        ('4300 == 4310-4320',
         lambda c: eq_pm(S('4300', c), (S('4310', c) or 0) - abs(S('4320', c) or 0))
         if all_have('4310', '4320', '4300') else None),
        ('4400 == 4100+4200+4300',
         lambda c: eq_pm(S('4400', c), sum(S(k, c) or 0 for k in ('4100', '4200', '4300')))
         if has(S('4400', c)) and all(S(k, c) is not None for k in ('4100', '4200', '4300')) else None),
        ('4500 == 4400+4450+4490',
         lambda c: eq(S('4500', c), (S('4400', c) or 0) + (S('4450', c) or 0) + (S('4490', c) or 0))
         if has(S('4500', c), S('4400', c), S('4450', c)) else None),
    ]
    for name, fn in rules:
        for c in range(n):
            try:
                r = fn(c)
            except Exception:
                r = None
            if r is False:
                fails.append(f'{name} [кол.{c}]')
    return fails


def same_printed_row(copy_vals, cand_vals):
    """Копия и строка-кандидат — это ОДНА И ТА ЖЕ напечатанная строка?

    Смотрим по заполненным колонкам КОПИИ: где у неё есть число, у кандидата должно быть то
    же число. Пустые колонки копии не сравниваются — `_sum_vals` в pipeline.py превращает
    None в 0, поэтому у копии и у оригинала пустые колонки расходятся.

    Почему не «нет колонки с двумя разными заполненными значениями» (это делает
    `pipeline._rows_repeat`): такая проверка склеила бы две РАЗНЫЕ напечатанные строки
    аренды — [None, 21, 379] и [10847, None, None], обе напечатаны у «ЕнисейАгроСоюз_6мес_2025».
    Вторая под неё не подходит: в кол.0 у копии 10847, а у неё пусто.
    """
    n = max(len(copy_vals or []), len(cand_vals or []))
    filled = 0
    for c in range(n):
        x = copy_vals[c] if c < len(copy_vals or []) else None
        y = cand_vals[c] if c < len(cand_vals or []) else None
        if x is None or x == 0:
            continue
        filled += 1
        if x != y:
            return False
    return filled > 0


def has_printed_twin(item, rows):
    """Есть ли среди rows другая строка с тем же именем и той же напечатанной строкой.

    Одна реализация на два места: `phantom_copies` (аудит дублей) и `rent_extract`
    (аренда). Раньше это были две вложенные функции с одинаковым телом.
    """
    nm = (item.get('name') or '').strip()
    vals = item.get('values') or []
    for other in rows:
        if other is item or (other.get('name') or '').strip() != nm:
            continue
        if same_printed_row(vals, other.get('values') or []):
            return True
    return False


def phantom_copies(balance):
    """Строки с пометкой `_absorbed_by_sum`, у которых в том же дереве есть двойник.

    Такая копия не несёт новой информации: ровно эта напечатанная строка уже видна в
    дереве. Но `merge_duplicate_codes` кладёт копию РЕБЁНКОМ поглотившей строки, поэтому
    всякий, кто суммирует вложенные строки, посчитает её второй раз. Именно так свод
    удваивал аренду: «ЕнисейАгроСоюз_6мес_2025» (1550 = 21 694 вместо 10 847) и
    «УПТК65_6мес_2025» (1550 = 41 112 вместо 20 556).

    Возвращает список словарей: имя, код, цепочка кодов и признак `phantom`. Строки без
    двойника — законные носители значения (19 из 20 в корпусе), их трогать не нужно.
    """
    rows = list(walk(balance.get('items')))

    out = []
    for it in rows:
        if not it.get('_absorbed_by_sum'):
            continue
        out.append({'name': it.get('name') or '',
                    'code': it.get('code'),
                    'chain': list(it.get('_chain') or []),
                    'phantom': has_printed_twin(it, rows)})
    return out


def rent_extract(balance, col_idx):
    """Арендные обязательства в колонке col_idx. Возвращает (long, short, notes, suspicion).
    long/short = None, если вкладов не найдено."""
    long_sum = 0
    short_sum = 0
    long_any = False
    short_any = False
    short_named = 0
    lease_in_kz = 0
    notes = []
    suspicion = False

    def vals_of(it):
        v = it.get('values') or []
        x = v[col_idx] if col_idx < len(v) else None
        return x

    # Если 1550 уже несёт собственную строку аренды, обязательство учтено в 1550, и
    # прибавлять ещё и аренду, найденную внутри 1520, значит посчитать её дважды.
    # Моторные технологии_6мес_2025: свод давал 9643 при эталоне 9410 (разница 233).
    lease_already_in_1550 = any(
        '1550' in (it.get('_chain') or []) and vals_of(it) is not None
        and (SHORT_RENT_RE.search(it.get('name') or '') or LEASE_RE.search(it.get('name') or ''))
        for it in walk(balance.get('items')))

    # Поглощённая копия (merge_duplicate_codes) существует ТОЛЬКО чтобы напечатанная
    # строка осталась видимой. Если такая строка в дереве уже есть, копия — фантом, и
    # считать её значит удвоить значение. Замеры:
    #   * «ЕнисейАгроСоюз_6мес_2025» — копия [10847, None, None] при такой же строке без кода;
    #   * «УПТК65_6мес_2025» — копия [20556, 0, 0] при строке [20556, None, None]: пустые
    #     колонки разошлись, потому что `_sum_vals` превращает None в 0. Свод давал
    #     1550 = 41 112 вместо 20 556, а 20 556 подтверждает сам отчёт: итог раздела V
    #     1 351 816 = 306 490 + 1 012 815 + 20 556 + 11 954 (плюс 1 на округление).
    all_rows = list(walk(balance.get('items')))

    for it in walk(balance.get('items')):
        name = it.get('name') or ''
        code = it.get('code')
        chain = it.get('_chain') or []
        if AVANS_RE.search(name) or code in ('1450', '1550'):
            continue
        if it.get('_absorbed_by_sum') and has_printed_twin(it, all_rows):
            notes.append(f'«{name}» col{col_idx}={vals_of(it)} — поглощённая копия, '
                         f'такая строка уже есть в дереве, не плюсовалась')
            continue
        m_long = bool(LONG_RENT_RE.search(name))
        m_short = bool(SHORT_RENT_RE.search(name))
        m_lease = bool(LEASE_RE.search(name)) and not (m_long or m_short)
        if not (m_long or m_short or m_lease):
            continue
        x = vals_of(it)
        vals = [x]
        desc = f'«{name}» [{"/".join(c for c in chain if c) or "верхний уровень"}] col{col_idx}={x}'
        if '1450' in chain or '1550' in chain:
            notes.append(desc + ' — внутри кода, не плюсовалась')
            continue
        if x is None:
            notes.append(desc + ' — null в целевой колонке')
            continue
        if m_long:
            long_sum += x
            long_any = True
            notes.append(desc + ' -> долгоср.')
        elif m_short:
            short_sum += x
            short_any = True
            short_named += 1
            notes.append(desc + ' -> краткоср.')
        else:
            chain_text = ' > '.join(chain)
            if '1520' in chain or code == '1520' or PARENT_SHORT_RE.search(chain_text):
                if lease_already_in_1550:
                    notes.append(desc + ' — 1550 уже содержит аренду, не плюсовалась')
                    continue
                short_sum += x
                short_any = True
                lease_in_kz += 1
                notes.append(desc + ' -> краткоср. (кредиторка/1520)')
            elif PARENT_LONG_RE.search(chain_text):
                long_sum += x
                long_any = True
                notes.append(desc + ' -> долгоср. (родитель)')
            else:
                suspicion = True
                short_sum += x
                short_any = True
                notes.append(desc + ' -> РОДИТЕЛЬ НЕ ОПРЕДЕЛЁН, сложено в краткоср.')
    if lease_in_kz and short_named:
        suspicion = True
        notes.append('ПОДОЗРЕНИЕ НА ДУБЛЬ: «Обязательство по аренде» в кредиторке + «Краткосрочные…аренд/лизинг» — сложены обе')
    return (long_sum if long_any else None), (short_sum if short_any else None), notes, suspicion


def main():
    data = {}
    for p in sorted(EXTRACTED.glob('*_6мес_*.json')):
        m = re.match(r'^(.*)_6мес_(\d{4})\.json$', p.name)
        if not m:
            continue
        d = load(p)
        for form_name in ('balance', 'income_statement', 'cash_flow'):
            if d.get(form_name):
                mark_chains(d[form_name])
        data[(m.group(1), int(m.group(2)))] = d

    table = {}      # emitter -> {(year, code): value}
    marks = {}      # emitter -> set((year, form))
    rent_susp = set()
    notes_all = {}

    for (emitter, year), d in sorted(data.items()):
        yk = str(year)
        bal, isf, cf = d.get('balance'), d.get('income_statement'), d.get('cash_flow')
        cells = table.setdefault(emitter, {})
        mk = marks.setdefault(emitter, set())

        bal_idx = col_index_balance(bal, year)
        if bal and bal_idx is None:
            notes_all.setdefault((emitter, yk), []).append(
                f'ВНИМАНИЕ: колонка «На 30 июня {year}» не найдена в balance.columns={bal.get("columns")}')

        # баланс (все коды + аренда)
        if bal and bal_idx is not None:
            for code in BAL_CODES:
                v = get_val(bal, code, bal_idx)
                if v is not None:
                    cells[(yk, code)] = v
            long_v, short_v, notes, susp = rent_extract(bal, bal_idx)
            base1450 = get_val(bal, '1450', bal_idx)
            base1550 = get_val(bal, '1550', bal_idx)
            if long_v is not None:
                cells[(yk, '1450')] = (base1450 or 0) + long_v
            elif base1450 is not None:
                cells[(yk, '1450')] = base1450
            if short_v is not None:
                cells[(yk, '1550')] = (base1550 or 0) + short_v
            elif base1550 is not None:
                cells[(yk, '1550')] = base1550
            if susp:
                rent_susp.add((emitter, yk))
            if notes:
                notes_all.setdefault((emitter, yk), []).extend('Аренда: ' + n for n in notes)

        # ОФР/ОДДС — только из файла-2026, обе колонки
        if year == 2026:
            for form_ru, form, codes in (('ОФР', isf, IS_CODES), ('ОДДС', cf, CF_CODES)):
                idx_cur, idx_prev, warn = flow_columns(form, year, form_ru)
                if warn:
                    notes_all.setdefault((emitter, yk), []).append(warn)
                    continue
                for code in codes:
                    for yy, idx in (('2026', idx_cur), ('2025', idx_prev)):
                        v = get_val(form, code, idx)
                        if v is not None:
                            cells[(yy, code)] = abs(v) if code == '2330' else v

        # пометки по нашим проверкам (по каждой форме)
        for form_name, form, fails in (
                ('баланс', bal, check_balance(bal)),
                ('ОФР', isf, check_is(isf)),
                ('ОДДС', cf, check_cf(cf))):
            if fails:
                mk.add((yk, form_name))
                notes_all.setdefault((emitter, yk), []).extend('CHECK ' + f for f in fails)

    out = {
        'table': {em: {f'{y}|{c}': v for (y, c), v in cells.items()} for em, cells in table.items()},
        'marks': {em: sorted(f'{y}:{f}' for (y, f) in m) for em, m in marks.items()},
        'rent_suspicious': sorted(f'{e}|{y}' for (e, y) in rent_susp),
        'notes': {f'{e}|{y}': n for (e, y), n in sorted(notes_all.items())},
    }
    DEBUG_PATH.parent.mkdir(exist_ok=True)
    DEBUG_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')

    print('файлов:', len(data))
    for em in EMITTERS + ORPHANS:
        has = [y for (e, y) in data if e == em]
        if not has:
            print(f'{em}: файлов нет')
            continue
        mr = out['marks'].get(em, [])
        susp = [s for s in out['rent_suspicious'] if s.startswith(em + '|')]
        filled = len(out['table'].get(em, {}))
        print(f'{em}: годы={has} ячеек={filled} marks={mr} rent_susp={susp}')
    print('\n-- CHECK-провалы --')
    for k, n in sorted(out['notes'].items()):
        for line in n:
            if line.startswith('CHECK'):
                print(k, line)


if __name__ == '__main__':
    main()
