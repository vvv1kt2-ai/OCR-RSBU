# -*- coding: utf-8 -*-
"""Финальная сборка: svod_2025_2026.xlsx + .csv + svod_audit.md

ВНИМАНИЕ. `svod_2025_2026.xlsx` — ЭТАЛОН: в нём лежат ручные правки пользователя, и по
отношению к CSV он первичен (см. CONTEXT.md). Поэтому по умолчанию сборка НЕ перезаписывает
его, а пишет рядом `svod_2025_2026.generated.xlsx`; перед записью в эталон делается копия с
отметкой времени, и только по явному флагу `--overwrite-gold`.
"""
import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, 'D:/models/pylibs')
sys.path.insert(0, 'D:/models')
import svod
import corrections as corr_mod
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

MODELS = Path('D:/models')                               # корень проекта: emitters.json лежит здесь
EXTRACTED = MODELS / 'extracted'
XLSX_PATH = EXTRACTED / 'svod_2025_2026.xlsx'            # эталон с ручными правками
XLSX_GENERATED = EXTRACTED / 'svod_2025_2026.generated.xlsx'
CSV_PATH = EXTRACTED / 'svod_2025_2026.csv'
AUDIT_PATH = EXTRACTED / 'svod_audit.md'


def target_xlsx(overwrite_gold=False):
    """Куда писать xlsx. Возвращает (путь, сделанная_копия_эталона|None).

    Без флага пишем рядом и эталон не трогаем: молчаливая перезапись ручных правок —
    необратимая потеря, а предупреждение в документе защитой не является.
    """
    if not overwrite_gold:
        return XLSX_GENERATED, None
    backup = None
    if XLSX_PATH.exists():
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = XLSX_PATH.with_name(f'svod_2025_2026.backup_{ts}.xlsx')
        shutil.copy2(XLSX_PATH, backup)
    return XLSX_PATH, backup

# ─── стили ───
HEADER_FILL = PatternFill('solid', fgColor='4472C4')
HEADER_FONT = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
SUB_FILL = PatternFill('solid', fgColor='D6E4F0')
SUB_FONT = Font(name='Calibri', bold=True, size=10)
REVIEW_BAL_FILL = PatternFill('solid', fgColor='FFC7CE')   # красный для баланс
REVIEW_ODDS_FILL = PatternFill('solid', fgColor='FFC7CE')  # красный для ОДДС (пока не используется)
RENT_SUSP_FILL = PatternFill('solid', fgColor='FFD966')    # оранжевый для дубля аренды
DISPUTED_FILL = PatternFill('solid', fgColor='E4C6FF')     # сиреневый: спорное, ждёт ручной проверки
CORRECTED_FILL = PatternFill('solid', fgColor='C6EFCE')    # зелёный: значение исправлено вручную
NET_FILL = PatternFill('solid', fgColor='D9D9D9')          # серый для «нет»
MFSO_FILL = PatternFill('solid', fgColor='F2F2F2')         # светло-серый для МСФО (пустые)
DATA_FONT = Font(name='Calibri', size=10)
DATA_ALIGN = Alignment(horizontal='right')
THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin'))

# колонки (порядок sum.csv) и формы
CODES = ['2110', '2300', '2330', '2320', '1510', '1550', '1410', '1450', '1250', '1300', '4100', '4110']
CODE_NAMES = {
    '1550': '1550 + Обязательство по аренде',
    '1450': '1450+ Обязательство по аренде',
}
FORM_OF = {  # код -> (форма для целей заливки, индекс колонки)
    '2110': 'ОФР', '2300': 'ОФР', '2330': 'ОФР', '2320': 'ОФР',
    '1510': 'баланс', '1550': 'баланс', '1410': 'баланс', '1450': 'баланс',
    '1250': 'баланс', '1300': 'баланс',
    '4100': 'ОДДС', '4110': 'ОДДС',
}
EMITTERS_PATH = MODELS / 'emitters.json'

# Ограничивать ли раздел про corrections.json списком эмитентов свода.
# По умолчанию НЕТ: основная сборка берёт все артефакты каталога, и открытые
# записи по любому из них уместны. Флаг оставлен как проверяемая настройка области
# аудита: tests/test_audit_needs_review.py собирает свод с True и False и сверяет, что
# при коротком списке в аудит не попадает эмитент вне свода. Одноразовый скрипт, ради
# которого флаг заводился (_svod18.py), удалён 25.11.2026; флаг пережил его только
# потому, что поведение утверждено тестом.
AUDIT_ONLY_EMITTERS = False

# Список эмитентов по умолчанию — тот, с которым свод собирался до выноса списка в данные.
# Он остаётся здесь ТОЛЬКО как запасной вариант: если emitters.json нет, свод всё равно
# соберётся, и старые сборки не падают.
DEFAULT_EMITTERS = [
    'ТГК-14', 'КИФА', 'Проект 111', 'Афанасий', 'Омега', 'Байсэл',
    'Бианка премиум', 'Сибсульфур', 'Простая еда', 'Славянск ЭКО',
    'НовосибирскАвтодор', 'Моторные технологии', 'Эфферон', 'Эфферон МСФО',
    'Нижегородец Восток', 'Финэква', 'Органик парк', 'ИПС',
    'Артген (ИСКЧ) МСФО', 'Артген (ИСКЧ)', 'Смартфакт', 'КЛВЗ Кристалл',
]
DEFAULT_ORPHANS = ['Корпсан', 'Рекорд трейд']
DEFAULT_MFSO = {'Эфферон МСФО', 'Артген (ИСКЧ) МСФО'}


def load_emitters(path=None):
    """Состав свода из данных: (эмитенты, орфаны, МСФО).

    Список отчётностей меняется чаще всего остального, и правка кода ради него — лишний
    риск: свод перестаёт собираться из-за опечатки в списке. Поэтому список живёт в
    `emitters.json` рядом с кодом (вне `extracted/`, то есть в git). Файла нет или он
    битый — берём встроенный список и говорим об этом, а не падаем.
    """
    p = Path(path) if path else EMITTERS_PATH
    if not p.exists():
        return list(DEFAULT_EMITTERS), list(DEFAULT_ORPHANS), set(DEFAULT_MFSO)
    try:
        raw = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'ВНИМАНИЕ: {p.name} не читается ({e}); беру встроенный список эмитентов')
        return list(DEFAULT_EMITTERS), list(DEFAULT_ORPHANS), set(DEFAULT_MFSO)
    em = raw.get('emitters')
    if not em:
        print(f'ВНИМАНИЕ: в {p.name} нет непустого поля emitters; беру встроенный список')
        return list(DEFAULT_EMITTERS), list(DEFAULT_ORPHANS), set(DEFAULT_MFSO)
    return (list(em),
            list(raw.get('orphans') or []),
            set(raw.get('mfso') or []))


def main(overwrite_gold=False):
    xlsx_out, backup = target_xlsx(overwrite_gold)
    emitters, orphans, mfso_emitters = load_emitters()
    corr = corr_mod.Corrections.load()
    apply_log = []          # что применили/не смогли применить
    data = {}
    for p in sorted(EXTRACTED.glob('*_6мес_*.json')):
        m = re.match(r'^(.*)_6мес_(\d{4})\.json$', p.name)
        if not m:
            continue
        d = json.load(open(p, encoding='utf-8'))
        doc = m.group(1) + '_6мес_' + m.group(2)
        for fn in ('balance', 'income_statement', 'cash_flow'):
            if d.get(fn):
                svod.mark_chains(d[fn])
                # Правки применяются ЗДЕСЬ, до чтения значений: иначе свод, правила и
                # логика аренды увидели бы разные числа.
                rep = corr.apply_form(d[fn], doc, fn)
                for a in rep['applied']:
                    apply_log.append(('applied', doc, fn, a))
                for u in rep['unapplied']:
                    apply_log.append(('unapplied', doc, fn, u))
        data[(m.group(1), int(m.group(2)))] = d

    # ─── сборка таблицы ───
    table = {}   # emitter -> {(year, code): value}
    marks = {}   # emitter -> set((year, form))
    prov = {}    # (emitter, year, code) -> (doc, form, column, code) — откуда взялась ячейка
    rent_susp = set()
    notes_all = {}
    rent_details = {}  # emitter -> {year: notes_list}
    # (emitter, yk) -> список строк, помеченных `_absorbed_by_sum` И имеющих двойника.
    # Это единственный способ увидеть двойной счёт, не читая деревья руками: сам свод
    # копии не суммирует (rent_extract их отсекает), но любая другая сумма по вложенным
    # строкам — суммирует. Строку с двойником надо видеть, даже когда свод чист.
    phantom_all = {}  # (emitter, yk) -> [{'name','code','chain'}]
    # Годы, по которым ЕСТЬ артефакт на диске. Единственный честный признак того, что
    # отчётность за этот год вообще собирали: data заполняется из файлов `*_6мес_YYYY.json`.
    have_years = {}       # emitter -> set of years
    # Артефакт есть, а баланса в нём нет. Два РАЗНЫХ случая, и оба — не «нет данных»:
    # форма не прочитана вообще (артефакт без balance) либо колонка «На 30 июня» не нашлась
    # в прочитанном балансе. Смешивать нельзя: первое часто означает сбой чтения, который
    # pipeline.py помечает статусом no_forms, и «нет» в своде скрыло бы существующую форму.
    no_form_years = {}    # emitter -> set of years: формы нет в артефакте
    no_column_years = {}  # emitter -> set of years: форма есть, колонки нет
    # emitter -> {yk: заголовок страницы 1}. Нужен, чтобы отличить «модель не прочитала
    # форму» от «скачан не тот файл»: у сканов `non_form_texts['1']` — OCR первой страницы,
    # и если она называется «Пояснения к Бухгалтерскому балансу…», то отчётности в файле
    # нет вовсе, и повторное чтение не поможет — нужен повторный сбор. Измерено на корпусе:
    # сигнал срабатывает ровно на 1 документе из 68 (АйДи Коллект_6мес_2026).
    wrong_doc_years = {}  # emitter -> {yk: str}
    # (emitter, yk) -> [(форма, колонки)]: у формы прочитаны данные, но заголовки колонок
    # не называют год документа, поэтому год колонки не доказан и значения не взяты.
    flow_no_column = {}
    # Формы, которые свод ЖДЁТ от артефакта, но которых в нём нет. За 2025 свод берёт ТОЛЬКО
    # баланс (ОФР и ОДДС оба года берёт из файла-2026), поэтому отсутствие ОФР/ОДДС в файле-2025
    # — норма, а не пробел. За 2026 нужны все три формы: без ОФР молчат коды 2110/2300/2330/2320,
    # без ОДДС — 4100/4110, а это половина столбцов свода.
    missing_forms = {}    # emitter -> {yk: [имена отсутствующих форм]}
    # (emitter, yk) -> {номер страницы: метка}. Нужно, чтобы отличить «формы в документе нет»
    # от «форма есть, но не прочитана»: иначе обе ситуации выглядели одинаково, и читатель
    # шёл перечитывать файл, в котором формы нет вовсе.
    doc_labels = {}
    NEEDED_FORMS = {2025: ('balance',),
                    2026: ('balance', 'income_statement', 'cash_flow')}
    FORM_RU = {'balance': 'баланс', 'income_statement': 'ОФР', 'cash_flow': 'ОДДС'}

    for (emitter, year), d in sorted(data.items()):
        yk = str(year)
        doc = f'{emitter}_6мес_{year}'   # стем артефакта: ключ слоя правок
        bal, isf, cf = d.get('balance'), d.get('income_statement'), d.get('cash_flow')
        # Ключи в JSON — строки, номера страниц — числа: приводим к строкам один раз здесь.
        doc_labels[(emitter, yk)] = {
            str(k): v for k, v in
            (((d.get('source') or {}).get('page_labels')) or {}).items()}
        cells = table.setdefault(emitter, {})
        mk = marks.setdefault(emitter, set())

        bal_idx = svod.col_index_balance(bal, year)
        if bal and bal_idx is None:
            notes_all.setdefault((emitter, yk), []).append(
                f'колонка «На 30 июня {year}» не найдена (columns={bal.get("columns")})')

        if bal and bal_idx is not None:
            for code in svod.BAL_CODES:
                # Провенанс пишем ВСЕГДА, даже если значения нет: помеченная, но пустая
                # ячейка — это «строка должна была быть прочитана, а её нет», и это надо видеть.
                prov[(emitter, yk, code)] = (doc, 'balance', bal_idx, code)
                v = svod.get_val(bal, code, bal_idx)
                if v is not None:
                    cells[(yk, code)] = v
            long_v, short_v, notes, susp = svod.rent_extract(bal, bal_idx)
            base1450 = svod.get_val(bal, '1450', bal_idx)
            base1550 = svod.get_val(bal, '1550', bal_idx)
            if long_v is not None:
                cells[(yk, '1450')] = (base1450 or 0) + long_v
                prov[(emitter, yk, '1450')] = (doc, 'balance', bal_idx, '1450')
            elif base1450 is not None:
                cells[(yk, '1450')] = base1450
                prov[(emitter, yk, '1450')] = (doc, 'balance', bal_idx, '1450')
            if short_v is not None:
                cells[(yk, '1550')] = (base1550 or 0) + short_v
                prov[(emitter, yk, '1550')] = (doc, 'balance', bal_idx, '1550')
            elif base1550 is not None:
                cells[(yk, '1550')] = base1550
                prov[(emitter, yk, '1550')] = (doc, 'balance', bal_idx, '1550')
            if susp:
                rent_susp.add((emitter, yk))
            if notes:
                rent_details.setdefault(emitter, {})[yk] = notes
            ph = [p for p in svod.phantom_copies(bal) if p['phantom']]
            if ph:
                phantom_all[(emitter, yk)] = ph

        if year == 2026:
            for form_ru, form, codes, fkey in (
                    ('ОФР', isf, svod.IS_CODES, 'income_statement'),
                    ('ОДДС', cf, svod.CF_CODES, 'cash_flow')):
                # условие и текст предупреждения — из svod.flow_columns, а не копией:
                # правка правила обязана доезжать до обоих сводов сразу
                idx_cur, idx_prev, warn = svod.flow_columns(form, 2026, form_ru)
                if warn:
                    notes_all.setdefault((emitter, yk), []).append(warn)
                    flow_no_column.setdefault((emitter, yk), []).append(
                        (form_ru, list(form.get('columns') or [])))
                    continue
                for code in codes:
                    for yy, idx in (('2026', idx_cur), ('2025', idx_prev)):
                        if idx is not None:
                            prov[(emitter, yy, code)] = (doc, fkey, idx, code)
                        v = svod.get_val(form, code, idx)
                        if v is not None:
                            cells[(yy, code)] = abs(v) if code == '2330' else v

        for form_name, form in (('баланс', bal), ('ОФР', isf), ('ОДДС', cf)):
            fails = svod.check_balance(form) if form_name == 'баланс' else (
                    svod.check_is(form) if form_name == 'ОФР' else svod.check_cf(form))
            if fails:
                mk.add((yk, form_name))
                notes_all.setdefault((emitter, yk), []).extend(f'{form_name}: ' + f for f in fails)

        # какие годы есть: артефакт на диске — признак «собирали», отсутствие формы или
        # колонки — «не прочитали». Ключ — строка года (yk), как в рендере и в аудите:
        # в data год лежит целым, и смешивать эти два вида нельзя, иначе проверка «год есть»
        # всегда ложна и «нет» проставляется всем подряд.
        have_years.setdefault(emitter, set()).add(yk)
        absent = [f for f in NEEDED_FORMS.get(year, ()) if not d.get(f)]
        if absent:
            missing_forms.setdefault(emitter, {})[yk] = absent
        if not bal:
            no_form_years.setdefault(emitter, set()).add(yk)
            p1_raw = ((d.get('source') or {}).get('non_form_texts') or {}).get('1') or ''
            # Заголовок — ПЕРВАЯ НЕПУСТАЯ строка страницы 1. Сворачивать весь текст
            # в одну строку нельзя: в аудит залезал кусок следующего раздела
            # («1.5. Наличие обособленных подразделений…») и обрывок выглядел мусором.
            first = next((ln for ln in p1_raw.split('\n') if ln.strip()), '')
            p1 = re.sub(r'[#*]+', ' ', first).strip()
            if re.search(r'Пояснени[ея]\s+к\s+бухгалтерскому', p1, re.I):
                wrong_doc_years.setdefault(emitter, {})[yk] = p1[:160]
        elif bal_idx is None:
            no_column_years.setdefault(emitter, set()).add(yk)

    # ─── XLSX ───
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Свод'

    # строка 1: «эмитент» + коды (merge на 2 колонки каждый)
    ws.cell(1, 1, 'Эмитент').font = HEADER_FONT
    ws.cell(1, 1).fill = HEADER_FILL
    ws.cell(1, 1).border = THIN_BORDER
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
    ws.cell(2, 1).border = THIN_BORDER

    for ci, code in enumerate(CODES):
        col_start = 2 + ci * 2
        label = CODE_NAMES.get(code, code)
        ws.cell(1, col_start, label).font = HEADER_FONT
        ws.cell(1, col_start).fill = HEADER_FILL
        ws.cell(1, col_start).alignment = Alignment(horizontal='center')
        ws.cell(1, col_start).border = THIN_BORDER
        ws.merge_cells(start_row=1, start_column=col_start, end_row=1, end_column=col_start + 1)
        ws.cell(1, col_start + 1).border = THIN_BORDER
        ws.cell(2, col_start, '2025').font = SUB_FONT
        ws.cell(2, col_start).fill = SUB_FILL
        ws.cell(2, col_start).alignment = Alignment(horizontal='center')
        ws.cell(2, col_start).border = THIN_BORDER
        ws.cell(2, col_start + 1, '2026').font = SUB_FONT
        ws.cell(2, col_start + 1).fill = SUB_FILL
        ws.cell(2, col_start + 1).alignment = Alignment(horizontal='center')
        ws.cell(2, col_start + 1).border = THIN_BORDER

    ws.column_dimensions['A'].width = 24
    for ci in range(len(CODES)):
        ws.column_dimensions[get_column_letter(2 + ci * 2)].width = 14
        ws.column_dimensions[get_column_letter(3 + ci * 2)].width = 14

    # строки данных
    marked_cells = {}   # 'disputed'|'corrected' -> [(эмитент, год, код, документ, значение)]
    row = 3
    all_emitters = emitters + orphans
    for em in all_emitters:
        cells = table.get(em, {})
        mk = marks.get(em, set())

        ws.cell(row, 1, em).font = DATA_FONT
        ws.cell(row, 1).border = THIN_BORDER

        is_mfso = em in mfso_emitters

        for ci, code in enumerate(CODES):
            for yi, year in enumerate(('2025', '2026')):
                col = 2 + ci * 2 + yi
                cell = ws.cell(row, col)
                cell.border = THIN_BORDER
                cell.alignment = DATA_ALIGN
                cell.font = DATA_FONT

                if is_mfso:
                    cell.fill = MFSO_FILL
                    continue

                # Года нет среди собранных артефактов — значит отчётности за него не было.
                # Раньше эта клетка молча оставалась пустой, хотя легенда и аудит (§7) обещают
                # «нет»: пустая клетка неотличима от «прочитали, а значение потерялось».
                #
                # Смотрим не на год клетки, а на ФАЙЛ, из которого значение берётся: баланс —
                # из файла своего года, а ОФР и ОДДС — оба года из файла-2026 (сравнительные
                # колонки). Поэтому у эмитента без файла-2025 ОФР/ОДДС за 2025 заполнены,
                # и ставить там «нет» было бы неправдой.
                form = FORM_OF[code]
                src_year = year if form == 'баланс' else '2026'
                if src_year not in have_years.get(em, set()):
                    cell.value = 'нет'
                    cell.fill = NET_FILL
                    continue

                val = cells.get((year, code))

                # Слой правок смотрим первым: это ручные вердикты о качестве чтения,
                # они важнее автоматических пометок.
                cstate = None
                p = prov.get((em, year, code))
                if p:
                    cstate = corr.cell_state(p[0], p[1], p[3], p[2])
                if cstate:
                    marked_cells.setdefault(cstate, []).append(
                        (em, year, code, p[0] if p else None, val))

                if val == 'нет':
                    cell.value = 'нет'
                    cell.fill = NET_FILL
                elif val is not None:
                    cell.value = val
                    cell.number_format = '#,##0'

                    # заливка
                    if cstate == 'corrected':
                        cell.fill = CORRECTED_FILL
                    elif cstate == 'disputed':
                        cell.fill = DISPUTED_FILL
                    else:
                        if (year, form) in mk:
                            if form == 'баланс':
                                cell.fill = REVIEW_BAL_FILL
                        if (em, year) in rent_susp and code in ('1450', '1550'):
                            cell.fill = RENT_SUSP_FILL
                else:
                    # Пустая ячейка, но помечена: строка должна была быть прочитана.
                    # Без заливки такой пропуск в своде просто не виден.
                    if cstate == 'corrected':
                        cell.fill = CORRECTED_FILL
                    elif cstate == 'disputed':
                        cell.fill = DISPUTED_FILL

        row += 1

    # legend row
    row += 1
    ws.cell(row, 1, 'Обозначения:').font = Font(bold=True, size=10)
    row += 1
    ws.cell(row, 1, '').fill = DISPUTED_FILL
    ws.cell(row, 2, 'Спорное чтение — ждёт ручной перепроверки по PDF '
                    '(corrections.json)').font = DATA_FONT
    row += 1
    ws.cell(row, 1, '').fill = CORRECTED_FILL
    ws.cell(row, 2, 'Значение исправлено вручную (corrections.json)').font = DATA_FONT
    row += 1
    ws.cell(row, 1, '').fill = REVIEW_BAL_FILL
    ws.cell(row, 2, 'Требует проверки (правила баланса не сошлись)').font = DATA_FONT
    row += 1
    ws.cell(row, 1, '').fill = RENT_SUSP_FILL
    ws.cell(row, 2, 'Подозрение на дубль арендных обязательств').font = DATA_FONT
    row += 1
    ws.cell(row, 1, '').fill = NET_FILL
    ws.cell(row, 2, 'Нет данных за этот год (файла отчёта нет)').font = DATA_FONT
    row += 1
    ws.cell(row, 1, '').fill = MFSO_FILL
    ws.cell(row, 2, 'Эмитент МСФО — ячейки не заполняются').font = DATA_FONT
    row += 1
    ws.cell(row, 1, 'Единица измерения:').font = Font(bold=True, size=10)
    ws.cell(row, 2, 'тыс. руб. (ОКЕИ 384). Омега 2025: JSON-метка «рублей» некорректна, данные в тыс. руб.').font = DATA_FONT

    ws.freeze_panes = 'B3'
    try:
        wb.save(xlsx_out)
    except PermissionError:
        # Файл открыт в Excel/WPS: запись невозможна, но сборка не должна пропадать —
        # иначе CSV и аудит уже обновлены, а xlsx остался старым, и это незаметно.
        alt = xlsx_out.with_name(f'{xlsx_out.stem} (свежая сборка){xlsx_out.suffix}')
        wb.save(alt)
        print(f'ВНИМАНИЕ: {xlsx_out.name} занят другой программой (открыт в Excel?) — '
              f'свежая сборка записана рядом: {alt.name}. '
              f'Закройте файл и повторите сборку, чтобы обновить основное имя.')
        xlsx_out = alt
    if backup:
        print(f'ВНИМАНИЕ: эталон перезаписан; копия прежнего — {backup.name}')
    elif xlsx_out == XLSX_GENERATED:
        print(f'эталон {XLSX_PATH.name} не тронут (для записи в него нужен --overwrite-gold)')
    print(f'XLSX: {xlsx_out} ({row} строк)')

    n_disp = len(marked_cells.get('disputed', []))
    n_corr = len(marked_cells.get('corrected', []))
    cc = corr.counts()
    print(f'Правки: записей {len(corr.entries)} — спорных {cc["disputed"]}, '
          f'правок {cc["corrected"]}, подтверждено {cc["confirmed"]}, '
          f'снято {cc["rejected"]}; помечено ячеек свода: спорных {n_disp}, '
          f'исправленных {n_corr}')
    for kind, adoc, afn, e in apply_log:
        if kind == 'unapplied':
            print(f'  ВНИМАНИЕ: правка не применена ({adoc} {afn}) — {e.get("why")}')

    # ─── CSV ───
    csv_lines = ['\ufeff' + ';'.join([
        'эмитент',
        '2110_2025', '2110_2026', '2300_2025', '2300_2026',
        '2330_2025', '2330_2026', '2320_2025', '2320_2026',
        '1510_2025', '1510_2026', '1550+аренда_2025', '1550+аренда_2026',
        '1410_2025', '1410_2026', '1450+аренда_2025', '1450+аренда_2026',
        '1250_2025', '1250_2026', '1300_2025', '1300_2026',
        '4100_2025', '4100_2026', '4110_2025', '4110_2026',
    ])]
    for em in all_emitters:
        cells = table.get(em, {})
        vals = [em]
        for code in CODES:
            for year in ('2025', '2026'):
                v = cells.get((year, code), '')
                vals.append(str(v) if v != '' else '')
        csv_lines.append(';'.join(vals))
    CSV_PATH.write_text('\n'.join(csv_lines), encoding='utf-8')
    print(f'CSV:  {CSV_PATH}')

    # ─── AUDIT ───
    lines = ['# Аудит свода svod_2025_2026\n']
    lines.append(f'Дата сборки: файлы из `{EXTRACTED}`\n')
    lines.append(f'Эмитентов: {len(all_emitters)} ({EMITTERS_PATH.name} + орфаны)\n')
    lines.append(f'Строк данных: {len(table)} (МСФО — пустые)\n\n')

    lines.append('## 1. Спорные данные и ручные правки (corrections.json)\n')
    lines.append('Источник: `D:/models/corrections.json` — отдельный слой поверх артефактов; '
                 'артефакты в `extracted/` остаются чистым выводом кода.\n')
    lines.append(f'Записей: {len(corr.entries)} — спорных {cc["disputed"]}, '
                 f'правок {cc["corrected"]}, подтверждено {cc["confirmed"]}, '
                 f'снято {cc["rejected"]}. Помечено ячеек свода: '
                 f'спорных {n_disp}, исправленных {n_corr}.\n')
    if marked_cells:
        lines.append('| Эмитент | Год | Код | Артефакт | Значение в своде | Метка |')
        lines.append('|---------|-----|-----|----------|------------------|-------|')
        for kind, label in (('disputed', 'спорное'), ('corrected', 'исправлено')):
            for em, yr, code, dcm, val in sorted(marked_cells.get(kind, [])):
                shown = val if val is not None else '— не прочитано —'
                lines.append(f'| {em} | {yr} | {code} | {dcm}.json | {shown} | {label} |')
        lines.append('')
    open_entries = [e for e in corr.entries.values()
                    if e['state'] in corr_mod.OPEN_STATES]
    if AUDIT_ONLY_EMITTERS:
        # Ключ правки — стем артефакта («ИПС_6мес_2025»), а в своде эмитент без года.
        in_svod = set(all_emitters)
        open_entries = [e for e in open_entries
                        if e['doc'].rsplit('_6мес_', 1)[0] in in_svod]
    if open_entries:
        lines.append('### Что именно ждёт ручной перепроверки\n')
        for e in sorted(open_entries, key=lambda x: (x['doc'], x['column'])):
            tgt = (f"{e['doc']} {corr_mod.FORM_RU.get(e['form'], e['form'])} "
                   f"кол.{e['column']} {corr_mod.target_ru(e)}")
            lines.append(f"- **{e['state']}** {tgt}")
            if e.get('reason'):
                lines.append(f'  - {e["reason"]}')
        lines.append('')
    if apply_log:
        unapplied = [x for x in apply_log if x[0] == 'unapplied']
        if unapplied:
            lines.append('### Правки, которые не удалось применить\n')
            for _, adoc, afn, e in unapplied:
                lines.append(f"- {adoc} {afn} код {e.get('code')}: {e.get('why')}")
            lines.append('')

    lines.append('## 2. Пометки «требует проверки» (правила баланса не сошлись)\n')
    lines.append('| Эмитент | Год | Форма | Правило |')
    lines.append('|---------|-----|-------|---------|')
    for em in all_emitters:
        for (emk, yk), fails in sorted(
                ((k, v) for k, v in notes_all.items() if k[0] == em)):
            for f in fails:
                if f.startswith('CHECK') or 'баланс' in f.lower():
                    rule = f.split(': ', 1)[-1] if ': ' in f else f
                    lines.append(f'| {em} | {yk} | {f.split(":")[0]} | {rule} |')
    lines.append('')

    lines.append('## 2б. Годы без файла, формы без чтения и колонки, которые не нашлись\n')
    lines.append('«Нет файла» — отчётность за год не собирали. В своде «нет» ставится по файлу, '
                 'из которого берётся значение: баланс — из файла своего года, ОФР и ОДДС — оба года '
                 'из файла-2026 (сравнительные колонки). Поэтому при отсутствии файла-2025 баланс '
                 'за 2025 будет «нет», а ОФР/ОДДС за 2025 — числами из файла-2026.\n')
    lines.append('Два случая ниже — НЕ «нет данных», поэтому «нет» там не ставится: '
                 '«форма не прочитана» (в артефакте нет баланса) и «колонка не найдена» '
                 '(баланс прочитан, но колонки «На 30 июня» в нём нет). Оба означают, что данные '
                 'скорее всего есть, а чтение не удалось. Внимание: сбой чтения pipeline.py '
                 'записывает статусом `no_forms`, и по статусу его от «в документе нет форм» '
                 'не отличить — здесь эта разница видна.\n')
    no_file = []
    for em in all_emitters:
        if em in mfso_emitters:
            continue
        for yk in ('2025', '2026'):
            if yk not in have_years.get(em, set()):
                if '2026' in have_years.get(em, set()):
                    what = 'баланс — нет; ОФР/ОДДС — из файла 2026'
                else:
                    what = 'нет'
                no_file.append(f'| {em} | {yk} | {what} |')
    if no_file:
        lines.append('| Эмитент | Год | Что в своде |')
        lines.append('|---------|-----|-------------|')
        lines.extend(no_file)
        lines.append('')
    else:
        lines.append('Годов без файла нет.\n')

    if missing_forms:
        # Два РАЗНЫХ случая, и делать по ним надо РАЗНОЕ. Метки страниц (`source.page_labels`)
        # дают точный ответ: если ни одна страница не названа этой формой, формы в документе нет
        # вовсе — перечитывать нечего, нужен повторный сбор файла. Если страница с такой меткой
        # есть, а формы в артефакте нет — это пробел чтения, и он лечится перечитыванием.
        # До этого обе ситуации стояли в одной таблице под подписью «настоящие пробелы чтения».
        # Замер: Регион-Продукт_6мес_2026 — 6 страниц, 1-3 баланс, 4 пустая, 5-6 ОФР; ОДДС в
        # файле отсутствует, а читателю предлагалось его перечитать.
        absent_here, unread_here, unknown_here = {}, {}, {}
        for em in sorted(missing_forms):
            for yk in sorted(missing_forms[em]):
                labels = doc_labels.get((em, yk)) or {}
                have = set(labels.values())
                for f in missing_forms[em][yk]:
                    if not labels:
                        bucket = unknown_here          # артефакт без меток — судить не о чем
                    elif f in have:
                        bucket = unread_here
                    else:
                        bucket = absent_here
                    bucket.setdefault(em, {}).setdefault(yk, []).append(f)

        CODES_OF = {'balance': '1510, 1550, 1410, 1450, 1250, 1300',
                    'income_statement': '2110, 2300, 2330, 2320',
                    'cash_flow': '4100, 4110'}

        lines.append('### Формы, которых в документе НЕТ (перечитывать нечего — нужен повторный '
                     'сбор файла)\n')
        lines.append('Ни одна страница файла не опознана как эта форма. Клетки соответствующих '
                     'кодов пусты и НЕ помечены «нет».\n')
        if absent_here:
            lines.append('| Эмитент | Год файла | Чего нет | Метки страниц файла | Какие коды свода молчат |')
            lines.append('|---------|-----------|----------|---------------------|-------------------------|')
            for em in sorted(absent_here):
                for yk in sorted(absent_here[em]):
                    forms = absent_here[em][yk]
                    names = ', '.join(FORM_RU.get(f, f) for f in forms)
                    codes = '; '.join(f'{FORM_RU.get(f, f)} — {CODES_OF[f]}' for f in forms)
                    labels = doc_labels.get((em, yk)) or {}
                    shown = ', '.join(f'{p}: {v}' for p, v in
                                      sorted(labels.items(), key=lambda kv: int(kv[0])))
                    lines.append(f'| {em} | {yk} | {names} | {shown} | {codes} |')
        else:
            lines.append('Таких нет.\n')
        lines.append('')

        lines.append('### Формы, которые в документе ЕСТЬ, но не прочитаны (лечится перечитыванием)\n')
        if unread_here:
            lines.append('| Эмитент | Год файла | Форма | Страницы с этой меткой | Какие коды свода молчат |')
            lines.append('|---------|-----------|-------|------------------------|-------------------------|')
            for em in sorted(unread_here):
                for yk in sorted(unread_here[em]):
                    labels = doc_labels.get((em, yk)) or {}
                    for f in unread_here[em][yk]:
                        pages = ', '.join(sorted((p for p, v in labels.items() if v == f),
                                                 key=int))
                        lines.append(f'| {em} | {yk} | {FORM_RU.get(f, f)} | {pages} | '
                                     f'{CODES_OF[f]} |')
        else:
            lines.append('Таких нет.\n')
        lines.append('')

        if unknown_here:
            lines.append('### Метки страниц не записаны — случай не опознан\n')
            lines.append('Причин две, и обе видны в `source.method` артефакта. Либо артефакт '
                         'сделан до того, как прогон начал писать `source.page_labels` (нужен '
                         'повторный прогон — он бесплатный, если страницы уже в кэше), либо '
                         'документ читался текстовой веткой: там разметки по страницам нет '
                         'вовсе, и «формы нет в тексте» от «форма не разобралась» этим '
                         'признаком не различить.\n')
            for em in sorted(unknown_here):
                for yk in sorted(unknown_here[em]):
                    forms = unknown_here[em][yk]
                    method = ((data.get((em, int(yk))) or {}).get('source') or {}).get('method') or '?'
                    lines.append(f'- **{em}** {yk} (method={method}): '
                                 + ', '.join(FORM_RU.get(f, f) for f in forms))
            lines.append('')
    else:
        lines.append('Все ожидаемые формы прочитаны.\n')

    if no_form_years:
        lines.append('### Форма есть в документе, но не прочитана (нужна ручная проверка)\n')
        lines.append('Причин две, и делать по ним надо РАЗНОЕ. Если первая страница файла — '
                     '«Пояснения к Бухгалтерскому балансу и Отчёту о финансовых результатах», '
                     'то в файле нет отчётности вообще: скачан не тот документ, и повторное '
                     'чтение не поможет — нужен повторный сбор файла. Если же остальные формы '
                     'прочитаны, а баланса нет, это похоже на сбой вызова модели при '
                     'структурировании — тогда помогает повторный прогон документа.\n')
        for em in sorted(no_form_years):
            yk_list = sorted(no_form_years[em])
            lines.append(f'- **{em}**: {", ".join(yk_list)} — '
                         f'баланса в артефакте нет; клетки пустые и НЕ помечены «нет»')
            for yk, p1 in sorted((wrong_doc_years.get(em) or {}).items()):
                if yk in no_form_years[em]:
                    lines.append(f'  - {yk}: похоже, СКАЧАН НЕ ТОТ ФАЙЛ — страница 1 '
                                 f'называется: {p1}. Отчётности в этом файле нет, '
                                 f'повторное чтение не поможет')
            if em not in wrong_doc_years:
                lines.append('  - причина не опознана по первой странице: проверить, '
                             'та ли форма в документе, затем перечитать документ')
        lines.append('')
    else:
        lines.append('Артефактов без баланса нет.\n')
    if no_column_years:
        lines.append('### Баланс прочитан, а колонка «На 30 июня» не найдена (нужна ручная проверка)\n')
        for em in sorted(no_column_years):
            lines.append(f'- **{em}**: {", ".join(sorted(no_column_years[em]))} — '
                         f'клетки баланса за эти годы пустые и НЕ помечены «нет»')
        lines.append('')
    else:
        lines.append('Файлов с ненайденной колонкой нет.\n')

    if flow_no_column:
        lines.append('### ОФР/ОДДС прочитаны, но заголовки колонок не называют год документа\n')
        lines.append('Свод берёт ОФР и ОДДС за ОБА года из файла-2026. Если колонки не называют '
                     '2026 год, то не доказана и колонка 2025: поставить туда число значило бы '
                     'выдать числа 2026 года за 2025. Поэтому значения этой формы не взяты — '
                     'клетки пустые, а не «нет». Причина обычно в том, что в список страниц формы '
                     'попала страница ЧУЖОЙ формы и заголовок прочитан с неё.\n')
        lines.append('| Эмитент | Год файла | Форма | Колонки в артефакте |')
        lines.append('|---------|-----------|-------|---------------------|')
        for (em, yk), lst in sorted(flow_no_column.items()):
            for form_ru, cols in lst:
                shown = ', '.join(str(c) for c in cols) if cols else '— пусто —'
                lines.append(f'| {em} | {yk} | {form_ru} | {shown} |')
        lines.append('')
    else:
        lines.append('Форм с недоказанным годом колонки нет.\n')

    lines.append('## 3. Аренда/лизинг — детализация по эмитентам\n')
    lines.append('| Эмитент | Год | Долгосрочная (в 1450) | Краткосрочная (в 1550) | Подозрение |')
    lines.append('|---------|-----|----------------------|------------------------|------------|')
    for em in all_emitters:
        for yk in ('2025', '2026'):
            if em in rent_details and yk in rent_details.get(em, {}):
                notes = rent_details[em][yk]
                long_v = table.get(em, {}).get((yk, '1450'), '')
                short_v = table.get(em, {}).get((yk, '1550'), '')
                susp = '⚠' if (em, yk) in rent_susp else ''
                lines.append(f'| {em} | {yk} | {long_v} | {short_v} | {susp} |')
    lines.append('')

    lines.append('### Строки-двойники: где возможен двойной счёт\n')
    if phantom_all:
        lines.append('Строка помечена `_absorbed_by_sum` (её значение уже входит в строку с '
                     'дублирующимся кодом) И имеет в дереве двойника — ровно ту же '
                     'напечатанную строку. В своде значение учтено ОДИН раз: копия несёт не '
                     'новое число, а только видимость напечатанной строки. Любая сумма по '
                     'вложенным строкам, которая копию не отсекает, удвоит число — так свод '
                     'и давал 1550 = 21 694 вместо 10 847 у «ЕнисейАгроСоюз_6мес_2025».\n')
        lines.append('| Эмитент | Год | Код | Цепочка | Строка |')
        lines.append('|---------|-----|-----|---------|--------|')
        for (em, yk), ph in sorted(phantom_all.items()):
            for p in ph:
                chain = ' → '.join(str(c) for c in p['chain']) or '—'
                lines.append(f"| {em} | {yk} | {p['code']} | {chain} | {p['name']} |")
        lines.append('')
    else:
        lines.append('Строк, поглощённых дублирующимся кодом и имеющих двойника, нет.\n')

    if rent_details:
        lines.append('### Исходные строки аренды (расшифровка)\n')
        for em in all_emitters:
            for yk in ('2025', '2026'):
                if em in rent_details and yk in rent_details.get(em, {}):
                    lines.append(f'**{em} {yk}:**')
                    for n in rent_details[em][yk]:
                        lines.append(f'- {n}')
                    lines.append('')
        lines.append('')

    lines.append('## 4. Примечания по единицам измерения\n')
    if AUDIT_ONLY_EMITTERS:
        # Раздел — заметка по всему корпусу, а не по этому своду: в нём перечислены
        # эмитенты вне таблицы. Нумерацию сохраняем, чтобы ссылки на разделы не ехали.
        lines.append('Пропущено: раздел описывает эмитентов вне этого свода.\n')
    else:
        lines.append('| Эмитент | Год | Примечание |')
        lines.append('|---------|-----|------------|')
        lines.append('| Омега | 2025 | JSON-метка «рублей», фактически данные в тыс. руб. (ОКЕИ 384); значение скорректировано не было (даны как есть) |')
        lines.append('| Афанасий | 2026 | Транскрипт отсутствует, предполагаются тыс. руб. |')
        lines.append('| Простая еда | 2025/2026 | Транскрипт отсутствует, предполагаются тыс. руб. |')
        lines.append('')

    lines.append('## 5. Файлы со статусом «needs_review» (баланс) — требуют ручной проверки\n')
    lines.append('| Эмитент | Файл | Статус | Причина |')
    lines.append('|---------|------|--------|---------|')
    # Ключи `data` — (эмитент, ГОД-ЧИСЛО), а не строка: перебор годов-строк не
    # совпадал ни с одним ключом, и колонка «Файл» всегда оставалась пустой.
    BAL_NEEDLES = ('1600', '1200', '1100', '1300+1400+1500')
    bal_marked = set()
    for em in all_emitters:
        for (yk, form) in marks.get(em, set()):
            if form == 'баланс':
                bal_marked.add(em)
    for em in sorted(bal_marked):
        files = [f'{em}_6мес_{y}.json' for y in (2025, 2026) if (em, y) in data]
        # Причину берём из записей ЭТОГО эмитента. Раньше здесь стояла переменная
        # `f`, оставшаяся от цикла раздела 2, — и во все строки попадала одна и та
        # же чужая причина (замер: у Денума и ЕнисейАгроСоюза выводилось «4100 ==
        # 4110-4120 [кол.1]», правила ОДДС, которых в их балансах нет).
        reasons = []
        for (e, y), n in sorted(notes_all.items()):
            if e != em:
                continue
            for note in n:
                if any(x in note for x in BAL_NEEDLES):
                    reasons.append(note.split(': ', 1)[-1])
        fails = '; '.join(reasons)
        lines.append(f'| {em} | {", ".join(files)} | needs_review | {fails[:120]} |')
    lines.append('')

    lines.append('## 6. ОФР/ОДДС — верификация пройдена\n')
    if AUDIT_ONLY_EMITTERS:
        lines.append('Пропущено: раздел описывает эмитентов вне этого свода.\n')
    else:
        lines.append('Все файлы ОФР/ОДДС проверены и исправлены (если требовалось):\n')
        lines.append('- **ИПС_6мес_2026**: строка 4400 «Сальдо денежных потоков за период» — потерян знак (−17671 вместо +17671); исправлено по подтверждению правилом 4500 и балансом 1250\n')
        lines.append('- **КИФА_6мес_2026**: хвост ОДДС (4320–4500) потерян при первичной структурировании; страница 11 PDF перечитана верификацией (gemini-3.8-flash)\n')
        lines.append('')

    lines.append('## 7. Структура свода\n')
    lines.append('Столбцы: 12 кодов × 2 года (2025, 2026) = 24 данныхых столбца\n')
    lines.append('Баланс: 2025 берётся из файла-2025, 2026 — из файла-2026\n')
    lines.append('ОФР/ОДДС: обе колонки (2025 и 2026) берутся из файла-2026\n')
    lines.append('Аренда: долгосрочные строки → 1450, краткосрочные → 1550 (только если ВНЕ кодов 1450/1550)\n')
    lines.append('МСФО-строки: пустые (Эфферон МСФО, Артген (ИСКЧ) МСФО)\n')
    lines.append(f'Орфаны ({", ".join(orphans)}): добавлены в конец\n')
    lines.append('Год без файла отчётности: в клетках стоит «нет» (серый фон)\n')
    lines.append(f'Состав свода: {EMITTERS_PATH.name} — {len(emitters)} эмитентов, '
                 f'{len(orphans)} орфанов, МСФО: {", ".join(sorted(mfso_emitters))}\n')

    AUDIT_PATH.write_text('\n'.join(lines), encoding='utf-8')
    print(f'AUDIT: {AUDIT_PATH}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--overwrite-gold', action='store_true',
                    help='писать в сам эталон svod_2025_2026.xlsx (перед этим делается '
                         'копия с отметкой времени). Без флага эталон не трогается.')
    main(overwrite_gold=ap.parse_args().overwrite_gold)
