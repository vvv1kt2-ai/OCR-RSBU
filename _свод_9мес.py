# -*- coding: utf-8 -*-
r"""Свод за 9 месяцев 2025 и 2026 — узкий, по составу рабочей таблицы.

Состав задан 20.11.2026: Эмитент · 2110 · 2300 · 2330 · 2320 · 1510 · 1550+аренда ·
1410 · 1450+аренда · 1250 · 1300 · 4100 · 4110, за 2025 и 2026.
Порядок строк — физический порядок рабочей таблицы (строки 2…140, включая разделитель
ФАКУЛЬТАТИВ), а не алфавит и не столбец «№№»: нумерация там дырявая.

Откуда какие числа:
  2026 — баланс, ОФР и ОДДС из отчёта 2026 года (текущая колонка);
  2025 — баланс из отчёта 2025 года (на 30.09.2025), а ОФР и ОДДС — из СРАВНИТЕЛЬНОЙ
         колонки отчёта 2026 года. Отдельный отчёт 2025 года нужен только ради баланса:
         ОФР за прошлый год в его состав не входит, а ОДДС в 2025 году не читается вовсе.

Аренда. «1550 + Обязательство по аренде» и «1450 + Обязательство по аренде» — это не
сложение кодов, а восстановление: в балансе аренда часто разложена по строкам-расшифровкам
внутри 1450/1550 либо попала в кредиторку. Логика взята из svod.py (`rent_extract`), чтобы
свод за 9 месяцев и прежний свод считали одинаково.

Запуск: python _свод_9мес.py
"""
import csv, json, os, re, sys, unicodedata

sys.path.insert(0, r'D:\models')
import pipeline as P
import svod

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRACTED = os.path.join(HERE, 'extracted')
# Порядок строк — вход, без которого свод не воспроизводится, поэтому он лежит рядом
# с кодом и отслеживается git, а не в tmp/. 25.11.2026 файл из tmp/ был удалён при чистке
# и восстановлен из _свод_9мес.json; повторять это незачем.
ROWS = os.path.join(HERE, '_свод_9мес.rows.txt')
OUT_CSV = os.path.join(HERE, '_свод_9мес.csv')
OUT_JSON = os.path.join(HERE, '_свод_9мес.json')

# (код, имя как в шапке рабочей таблицы, источник)
METRICS = [
    ('2110', 'Выручка, тыс.руб.', 'isf'),
    ('2300', 'Прибыль до налогов, тыс.руб.', 'isf'),
    ('2330', '% к уплате', 'isf'),
    ('2320', '% к получению', 'isf'),
    ('1510', 'Краткосрочный долг (до 1 года)', 'bal'),
    ('1550', 'Прочие обяз., краткосрочные + аренда', 'bal_rent_short'),
    ('1410', 'Долгосрочный долг (заёмные)', 'bal'),
    ('1450', 'Прочие обяз., долгосрочные + аренда', 'bal_rent_long'),
    ('1250', 'Денежные средства', 'bal'),
    ('1300', 'Капитал', 'bal'),
    ('4100', 'Сальдо ДП от текущих операций', 'cf'),
    ('4110', 'Поступления ДС из ОДДС', 'cf'),
]

# Ручные соответствия: имя в рабочей таблице -> имя файла извлечения.
OVERRIDES = {
    'Интернешнл Петролеум Сервис (ИПС)': 'Интернешнл Петролеум Сервис (ИПС)',
    'Инженерные Системы Пожаробезопасности (ИСП)': 'Инженерные Системы Пожаробезопасности (ИСП)',
    'КЛС-Трейд (Интерскол)': 'КЛС-Трейд (Интерскол)',
    'Рольф (Промагрологистика)': 'Рольф (Промагрологистика)',
    'СЭЗ им. Серго Орджоникидзе': 'СЭЗ им. Серго Орджоникидзе',
}


def norm(s):
    s = unicodedata.normalize('NFKC', s or '').lower()
    s = re.sub(r'[«»"\'`]', '', s)
    s = re.sub(r'\b(ооо|ао|пао|зао|оао|нао)\b', '', s)
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'[^0-9a-zа-яё]+', '', s)
    return s


LINK_STATUS_OK = ('uploaded', 'unchanged', 'replaced')


def load_links():
    """Ссылки из _links_9m_<год>.csv, только реально загруженные.

    Строка со статусом planned — это ещё не ссылка: файла в бакете нет, и в таблице она
    дала бы битый адрес. Поэтому берутся только uploaded/unchanged/replaced.
    """
    out = {}
    for year in (2025, 2026):
        path = os.path.join(HERE, f'_links_9m_{year}.csv')
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f, delimiter=';'):
                if (row.get('статус') or '').split(':')[0] in LINK_STATUS_OK:
                    stem = os.path.splitext(row.get('файл') or '')[0]
                    if stem:
                        out.setdefault(stem, {})[year] = row.get('ссылка')
    return out


def load_artifacts():
    """{нормализованное имя: {2025: data, 2026: data}}"""
    out = {}
    for p in sorted(os.listdir(EXTRACTED)):
        m = re.match(r'^(.*)_9мес_(\d{4})\.json$', p)
        if not m:
            continue
        stem, year = m.group(1), int(m.group(2))
        try:
            d = json.load(open(os.path.join(EXTRACTED, p), encoding='utf-8'))
        except Exception:
            continue
        out.setdefault(norm(stem), {})[year] = d
    return out


def bal_idx(bal, year):
    """Индекс колонки «на 30 сентября {year}».

    Три равноправных написания, все встречаются в корпусе:
      «На 30 сентября 2026 г.»  — печатная шапка;
      «2026-09-30»              — ISO, так пишет часть эмитентов;
      «30.09.2026»              — числовая запись.
    Раньше искались только русские месяцы, и документы с ISO-шапкой молча получали пустой
    баланс: замер 20.11.2026 — «Бианка премиум_9мес_2026», 1450 = 361 916 в артефакте,
    в своде пусто.

    Год ищется общим `svod.year_pattern`, а не локальной регуляркой: транскрипция иногда
    отдаёт «На 30 сентября 20 26 г.» с пробелом внутри числа, и непрерывная подстрока
    такую колонку теряет. Замер 25.11.2026 — «Село Зеленое_9мес_2025» и «Простая
    еда_9мес_2025»: баланс в артефакте есть, в своде пусто.
    """
    if not bal:
        return None
    y = str(year)
    iso = f'{y}-09-30'
    dotted = f'30.09.{y}'
    pat = re.compile(r'30\s*сентябр\w*\s*' + svod.year_pattern(year).pattern, re.I)
    for i, c in enumerate(bal.get('columns') or []):
        cs = str(c).strip()
        if cs == iso or cs.startswith(iso) or cs.replace(' ', '') == dotted:
            return i
        if pat.search(cs):
            return i
    return None


def flow_idx(form, year):
    """Индекс колонки ОФР/ОДДС за {year}; год берётся тем же шаблоном, что в svod.py.

    Своя регулярка здесь была четвёртой копией правила и уже разошлась с svod.py:
    колонка «За 9 мес 20 26 г.²» не находилась, и ОДДС молча уходил в нули.
    """
    if not form:
        return None
    pat = svod.year_pattern(year)
    for i, c in enumerate(form.get('columns') or []):
        if pat.search(str(c)):
            return i
    return None


def code_in(form, code):
    """Есть ли код строки в форме. Отличает «прочерк» от «строки нет вовсе»."""
    return any(it.get('code') == code for it in (form or {}).get('items') or [])


def cell_value(v, readable):
    """Что писать в клетку свода.

    readable — колонка нужного года найдена И код строки в форме присутствует.
    Тогда None означает прочерк в отчёте, и это ноль. Иначе None означает «не читали»,
    и клетка остаётся пустой: «нет данных» и «данные равны нулю» — разные утверждения
    (`_СВОД_9мес_ОТЧЁТ.md` §7.3).
    """
    if v is not None:
        return v
    return 0 if readable else ''


def pick(doc, form_key, idx, code):
    if not doc or idx is None:
        return None
    return svod.get_val(doc.get(form_key), code, idx)


def failed_cols(doc, form_key):
    """Индексы колонок, где правило формы НЕ сошлось (verdict=fail).

    Нужно, чтобы подсветить конкретное значение, а не всю строку: если не сошёлся баланс
    в колонке 2026, то и 1300, и 1250 за 2026 требуют проверки, а значения за 2025 —
    нет, они из другого отчёта.
    """
    out = set()
    for c in (doc or {}).get('checks') or []:
        if c.get('form') != form_key or c.get('verdict') != 'fail':
            continue
        for i, v in enumerate(c.get('per_column') or []):
            if v is False:
                out.add(i)
    return out


def build_row(arts, name):
    key = norm(name)
    pair = arts.get(key) or arts.get(norm(OVERRIDES.get(name, name))) or {}
    d26, d25 = pair.get(2026), pair.get(2025)
    row, readable, risk = {}, {}, {}
    for year in (2025, 2026):
        bal = (d26 if year == 2026 else d25) or {}
        bi = bal_idx(bal.get('balance'), year)
        # аренда считается по тому же балансу, из которого взяты 1450/1550.
        # mark_chains ОБЯЗАТЕЛЕН: без него у строк нет _chain, и проверка «аренда внутри
        # кода 1450» не срабатывает — тогда «в том числе» прибавляется к самому 1450 и
        # сумма удваивается. Замер 20.11.2026, «Спектр_9мес_2026»: 1450 = 13 832 940,
        # аренда той же величиной внутри него, свод давал 27 665 880.
        long_v = short_v = None
        if bi is not None and bal.get('balance'):
            svod.mark_chains(bal['balance'])
            long_v, short_v, _n, _s = svod.rent_extract(bal.get('balance'), bi)
        # ОФР/ОДДС за оба года — из отчёта 2026: 2026 из текущей колонки, 2025 из
        # сравнительной. Отдельный отчёт 2025 года нужен только ради баланса.
        src = d26
        ii = flow_idx(src.get('income_statement'), year) if src else None
        ci = flow_idx(src.get('cash_flow'), year) if src else None
        _bal_doc = d26 if year == 2026 else d25
        _fbal = failed_cols(_bal_doc, 'balance')
        _fisf = failed_cols(d26, 'income_statement')
        _fcf = failed_cols(d26, 'cash_flow')
        for code, _label, kind in METRICS:
            # читаемо = колонка нужного года найдена И есть откуда взять число:
            # либо код строки присутствует в форме, либо для 1450/1550 нашлась аренда
            # (она может лежать в кредиторке/1520 при отсутствующей строке 1550 — замер
            # 25.11.2026: СПМК, АйДи Коллект, УПТК65). Одного «форма есть» мало: при
            # отсутствующей колонке pick вернёт None по всем кодам сразу, и признак
            # «читаемо» превращал бы всю колонку в нули.
            if kind.startswith('bal'):
                form, idx = bal.get('balance'), bi
            elif kind == 'isf':
                form, idx = (src or {}).get('income_statement'), ii
            else:
                form, idx = (src or {}).get('cash_flow'), ci
            rent = (long_v if kind == 'bal_rent_long'
                    else short_v if kind == 'bal_rent_short' else None)
            readable[(code, year)] = idx is not None and (code_in(form, code) or rent is not None)
            if kind == 'bal':
                v = pick(bal, 'balance', bi, code)
            elif kind == 'bal_rent_long':
                # base or 0: отсутствующая строка 1450 при найденной аренде означает, что
                # аренда и есть всё содержимое кода, а не что числа нет
                base = pick(bal, 'balance', bi, code)
                v = (base or 0) + long_v if long_v is not None else base
            elif kind == 'bal_rent_short':
                base = pick(bal, 'balance', bi, code)
                v = (base or 0) + short_v if short_v is not None else base
            elif kind == 'isf':
                v = pick(src, 'income_statement', ii, code)
            else:
                v = pick(src, 'cash_flow', ci, code)
            row[(code, year)] = v
            # значение попадает в «требует проверки», если его форма не сошлась
            # именно в этой колонке
            if kind.startswith('bal'):
                risk[(code, year)] = bi is not None and bi in _fbal
            elif kind == 'isf':
                risk[(code, year)] = ii is not None and ii in _fisf
            else:
                risk[(code, year)] = ci is not None and ci in _fcf
    return row, readable, risk, (d25 is not None), (d26 is not None)


def main():
    arts = load_artifacts()
    links = load_links()
    print('артефактов в индексе:', len(arts))

    rows = []
    if not os.path.exists(ROWS):
        # Внятное сообщение вместо трейсбека: файл — вход, а не кэш, и его отсутствие
        # означает, что порядок строк неизвестен, а не что «строк нет».
        sys.exit(f'нет файла порядка строк: {ROWS}\n'
                 f'Это вход свода (139 строк вида «номер|ответственный|эмитент», разделитель '
                 f'ФАКУЛЬТАТИВ на 126). Восстанавливается из листа «Свод» собранного xlsx '
                 f'(столбцы A и B) или из _свод_9мес.json.')
    for line in open(ROWS, encoding='utf-8'):
        parts = line.rstrip('\n').split('|')
        if len(parts) != 3:
            continue
        num, resp, name = parts[0], parts[1].strip(), parts[2].strip()
        rows.append((int(num), resp, name))

    header1 = ['Распределение ответственных', 'Эмитент']
    header2 = ['', '']
    for code, label, _k in METRICS:
        for year in (2025, 2026):
            header1.append(f'{label} ({code})')
            header2.append(f'3 кв {year}')
    header1.append('Статус 2026')
    header2.append('для проверки')
    header1 += ['Отчёт 2026', 'Отчёт 2025']
    header2 += ['PDF', 'PDF']

    out, quality = [], []
    filled = 0
    for num, resp, name in rows:
        if name == 'ФАКУЛЬТАТИВ':
            out.append(['', 'ФАКУЛЬТАТИВ'] + [''] * (len(header1) - 2))
            quality.append([num, 'ФАКУЛЬТАТИВ', '', '', '', '', '', ''])
            continue
        vals, readable, risk, has25, has26 = build_row(arts, name)
        line = [resp, name]
        dashes, risky = [], []
        for code, _label, _k in METRICS:
            for year in (2025, 2026):
                v = vals.get((code, year))
                # Прочерк в отчёте — это ноль, но только там, где форма прочитана и строка
                # в ней есть. Пустая клетка из-за отсутствующей колонки или отсутствующего
                # кода нулём не становится: «нет данных» и «данные равны нулю» — разные
                # утверждения. Разбор — в cell_value().
                if v is None and readable.get((code, year)):
                    dashes.append(f'{code}_{year}')
                if risk.get((code, year)) and v is not None:
                    risky.append(f'{code}_{year}')
                line.append(cell_value(v, readable.get((code, year))))
        if any(v is not None for v in vals.values()):
            filled += 1
        # Статус строки — худший из двух отчётов: баланс 2025 берётся из отчёта 2025 года,
        # и если там форма не сошлась или не прочитана, строка требует проверки независимо
        # от того, что отчёт 2026 года в порядке. Иначе 5 замечаний по отчётам 2025 года
        # (Л-старт, Векус, Эфферон, НовосибирскАвтодор, Трансконтейнер) выпадали из свода.
        _pair = arts.get(norm(name)) or {}
        _sts = [(_pair.get(y) or {}).get('status') for y in (2026, 2025)]
        _bad = [x for x in _sts if x in ('needs_review', 'incomplete', 'no_forms')]
        st26 = 'needs_review' if _bad else ('ok' if 'ok' in _sts else '')
        line.append(st26)
        # ссылки: ищем по имени файла извлечения, а не по названию эмитента
        pair = arts.get(norm(name)) or {}
        for year in (2026, 2025):
            d = pair.get(year) or {}
            src = (d.get('source') or {}).get('file') or ''
            stem = os.path.splitext(src)[0]
            line.append(links.get(stem, {}).get(year, ''))
        out.append(line)
        quality.append([num, name, 'есть' if has25 else 'нет', 'есть' if has26 else 'нет',
                        sum(1 for v in vals.values() if v is not None), st26,
                        ';'.join(dashes), ';'.join(risky)])

    with open(OUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(header1)
        w.writerow(header2)
        w.writerows(out)

    json.dump({'header1': header1, 'header2': header2, 'rows': out,
               'quality': quality}, open(OUT_JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    print(f'строк: {len(out)}, из них с данными: {filled}')
    no26 = [q[1] for q in quality if q[2] != 'ФАКУЛЬТАТИВ' and q[3] == 'нет']
    print(f'без отчёта 2026: {len(no26)} -> {", ".join(no26[:8])}{" ..." if len(no26) > 8 else ""}')
    print(f'-> {OUT_CSV}')


if __name__ == '__main__':
    main()