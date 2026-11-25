# -*- coding: utf-8 -*-
"""Слой ручных правок и пометок «спорное» поверх артефактов извлечения РСБУ.

Зачем отдельный файл
--------------------
Цель проекта — проверять ПРАВИЛЬНОСТЬ ПРОЧИТАННЫХ ЦИФР, а не приводить отчёт в порядок.
Значит нужно уметь ответить на вопрос «где именно модель прочитала неверно». Если правки
живут внутри артефактов, то при любой пересборке они смешиваются с выводом кода и метрика
теряется. Поэтому:

    артефакт (extracted/*.json)  = чистый вывод кода, воспроизводим
    corrections.json             = слой поверх: пометки «спорное» + ручные правки

Артефакты на диске этот модуль НИКОГДА не меняет. `apply_*` работают в памяти, и их
результат использует сборка свода.

Ключ записи
-----------
    (doc, form, column, code)

- `doc`    — стем артефакта, например `ИПС_6мес_2025`;
- `form`   — `balance` | `income_statement` | `cash_flow`;
- `column` — индекс колонки в форме (как в `form['columns']`);
- `code`   — код строки, либо `None` для спора про ВСЮ колонку (тогда `codes` — список
             подозреваемых кодов).

Ключ намеренно НЕ содержит ни списка эмитентов, ни списка кодов свода. Список отчётностей
меняется почти наверняка, список метрик — реже; ключ от них не зависит, поэтому правки
переживают обе перестройки. Записи про коды, выпавшие из свода, не пропадают — `reconcile`
показывает их как `orphan`.

Состояния
---------
- `disputed`  — помечено как спорное, ждёт ручной перепроверки (значение НЕ меняется);
- `corrected` — прочитано неверно, задано верное значение (`value_final`);
- `confirmed` — проверено вручную, прочитано верно (пометка снимается);
- `rejected`  — пометка снята как ложная тревога (правило дало ложный провал).

`disputed` и `corrected` дают заливку в своде; `confirmed` и `rejected` — закрытые
состояния, они остаются в файле как след проверки.

История
-------
Каждая запись несёт `history` — список переходов. Записи не удаляются и не переписываются
задним числом: новое состояние дописывается в `history`, поэтому `git log -p corrections.json`
показывает, когда и почему пометка появилась и чем закончилась.

CLI
---
    python corrections.py --list                 # что сейчас помечено
    python corrections.py --reconcile            # сходятся ли пометки с артефактами

    # пометить спор про колонку (коды подозреваются, но неясно, какой именно):
    python corrections.py --mark ИПС_6мес_2025 balance 0 \
        --codes 1520,1530,1550 --rule "1500 == 1510+1520+1530+1540+1550" \
        --reason "строки не прочитаны"

    # записать конкретную правку после сверки с PDF:
    python corrections.py --mark Корпсан_6мес_2026 balance 0 --code 1520 \
        --state corrected --value-read 221227 --value-final 219502 \
        --reason "сверил с PDF, стр. 3"

    # закрыть пометку (проверено вручную / ложная тревога):
    python corrections.py --mark ИПС_6мес_2025 balance 0 --codes 1520,1530,1550 \
        --state confirmed --reason "перечитал, значения верны"

Повторный `--mark` по тому же (doc, form, column, code) не создаёт вторую запись, а
дописывает переход в `history` — поэтому `git log -p corrections.json` показывает
историю проверки.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r'D:\models')
import svod

MODELS = Path('D:/models')
EXTRACTED = MODELS / 'extracted'
CORRECTIONS_PATH = MODELS / 'corrections.json'

FORMS = ('balance', 'income_statement', 'cash_flow')
FORM_RU = {'balance': 'баланс', 'income_statement': 'ОФР', 'cash_flow': 'ОДДС'}

# Открытые состояния дают заливку в своде; закрытые — только след в файле.
OPEN_STATES = ('disputed', 'corrected')
CLOSED_STATES = ('confirmed', 'rejected')
STATES = OPEN_STATES + CLOSED_STATES

# Как состояние записи соотносится с текущим значением в артефакте (см. reconcile).
ACTIVE, STALE, DRIFTED, CLOSED, NO_ROW = 'active', 'stale', 'drifted', 'closed', 'no_row'


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def make_key(doc, form, column, code):
    """`doc|form|column|code`, где отсутствующий код записывается как `*`."""
    return f'{doc}|{form}|{column}|{code if code is not None else "*"}'


def parse_key(k):
    doc, form, col, code = k.split('|')
    return doc, form, int(col), (None if code == '*' else code)


def doc_parts(doc):
    """`ИПС_6мес_2025` -> ('ИПС', 2025). None, если стем не по шаблону."""
    m = re.match(r'^(.*)_6мес_(\d{4})$', doc)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def _get_val(form, code, idx):
    """Значение кода в колонке idx — из ПОСЛЕДНЕГО верхнеуровневого item с этим кодом.

    Реализация — `svod.get_val`, а не копия: правка обязана попадать ровно в ту ячейку,
    которую читает свод, и вторая копия правила уже была источником расхождений.
    """
    return svod.get_val(form, code, idx)


def _set_val(form, code, idx, value):
    """Записать значение в ту же ячейку, которую читает `_get_val`. True, если удалось."""
    items = [it for it in (form.get('items') or []) if it.get('code') == code]
    if not items:
        return False
    it = items[-1]
    vals = it.setdefault('values', [])
    while len(vals) <= idx:
        vals.append(None)
    vals[idx] = value
    return True


class Corrections:
    """Слой правок. `entries` — словарь `key -> запись`, порядок вставки сохраняется."""

    def __init__(self, entries=None, path=CORRECTIONS_PATH):
        self.path = Path(path)
        self.entries = entries if entries is not None else {}

    # ─── загрузка/сохранение ───

    @classmethod
    def load(cls, path=CORRECTIONS_PATH):
        p = Path(path)
        if not p.exists():
            return cls({}, p)
        raw = json.loads(p.read_text(encoding='utf-8'))
        entries = {}
        for e in raw.get('entries') or []:
            k = e.get('key') or make_key(e['doc'], e['form'], e['column'], e.get('code'))
            e['key'] = k
            entries[k] = e
        return cls(entries, p)

    def to_dict(self):
        return {
            'version': 1,
            'about': ('Слой ручных правок и пометок «спорное» поверх артефактов извлечения. '
                      'Артефакты в extracted/ — чистый вывод кода; здесь только то, что '
                      'требует человеческого глаза. Записи не удаляются: новое состояние '
                      'дописывается в history, поэтому историю видно через git.'),
            'states': {
                'disputed': 'спорное, ждёт ручной перепроверки (значение не меняется)',
                'corrected': 'прочитано неверно, задано верное значение (value_final)',
                'confirmed': 'проверено вручную, прочитано верно',
                'rejected': 'пометка снята как ложная тревога',
            },
            'updated': now_iso(),
            'entries': list(self.entries.values()),
        }

    def save(self, path=None):
        p = Path(path) if path else self.path
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + '\n',
                     encoding='utf-8')
        return p

    # ─── запись ───

    def record(self, doc, form, column, code=None, codes=None, rule=None,
               state='disputed', value_read=None, value_final=None,
               reason='', source='human', at=None):
        """Создать запись или перевести существующую в новое состояние.

        Существующая запись не перезаписывается: меняются `state`/`value_final`, а переход
        дописывается в `history`. Так файл остаётся следом проверки, а не текущим снимком.
        """
        if state not in STATES:
            raise ValueError(f'неизвестное состояние: {state!r} (ожидается одно из {STATES})')
        if state == 'corrected' and value_final is None:
            raise ValueError('состояние corrected требует value_final')
        at = at or now_iso()
        k = make_key(doc, form, column, code)
        e = self.entries.get(k)
        if e is None:
            e = {
                'key': k, 'doc': doc, 'form': form, 'column': column,
                'code': code, 'codes': list(codes) if codes else None,
                'rule': rule, 'state': state,
                'value_read': value_read, 'value_final': value_final,
                'reason': reason, 'source': source, 'history': [],
            }
            self.entries[k] = e
        else:
            e['state'] = state
            if value_final is not None:
                e['value_final'] = value_final
            if reason:
                e['reason'] = reason
            if rule:
                e['rule'] = rule
            if codes:
                e['codes'] = list(codes)
        e['history'].append({
            'at': at, 'state': state, 'by': source,
            'value_read': e.get('value_read'), 'value_final': e.get('value_final'),
            'note': reason,
        })
        return e

    # ─── чтение ───

    def entry_for_cell(self, doc, form, code, column):
        """Запись, определяющая состояние ячейки (doc, form, code, column), или None.

        Приоритет: запись ПО КОНКРЕТНОМУ коду перебивает запись про всю колонку. Иначе
        пометка «проверить 1520/1530/1550» не снималась бы по одной ячейке: человек
        проверил 1520, закрыл её — а колонка продолжала бы красить её как спорную, и
        отличить проверенное от непроверенного стало бы нельзя.
        """
        exact = self.entries.get(make_key(doc, form, column, code))
        if exact is not None:
            return exact
        wild = self.entries.get(make_key(doc, form, column, None))
        if wild is not None and (not wild.get('codes') or code in wild['codes']):
            return wild
        return None

    def cell_state(self, doc, form, code, column):
        """Заливка для ячейки свода: None | 'disputed' | 'corrected'.

        Закрытые состояния (`confirmed`, `rejected`) заливки не дают — это след проверки,
        а не требование действия.
        """
        e = self.entry_for_cell(doc, form, code, column)
        if e is None:
            return None
        return {'corrected': 'corrected', 'disputed': 'disputed'}.get(e['state'])

    def column_entries(self, doc=None, form=None, column=None):
        out = []
        for e in self.entries.values():
            if doc is not None and e['doc'] != doc:
                continue
            if form is not None and e['form'] != form:
                continue
            if column is not None and e['column'] != column:
                continue
            out.append(e)
        return out

    def counts(self):
        c = {s: 0 for s in STATES}
        for e in self.entries.values():
            c[e['state']] = c.get(e['state'], 0) + 1
        return c

    # ─── применение к артефакту (в памяти) ───

    def apply_form(self, form, doc, form_name):
        """Применить правки к форме, вернуть отчёт о применении.

        Артефакт на диске не трогается: правки живут только на время сборки свода.
        Возвращает {'applied': [...], 'unapplied': [...]}.
        """
        applied, unapplied = [], []
        for e in self.entries.values():
            if e['doc'] != doc or e['form'] != form_name:
                continue
            if e['state'] != 'corrected':
                continue
            code, col = e.get('code'), e['column']
            if code is None:
                unapplied.append({**e, 'why': 'правка про всю колонку — применять некуда'})
                continue
            cur = _get_val(form, code, col)
            if cur is None and not any(
                    it.get('code') == code for it in (form.get('items') or [])):
                # Строки нет вовсе. Это НЕ «значение пустое», а пропущенная строка:
                # записывать её в артефакт нельзя — она не была прочитана.
                unapplied.append({**e, 'why': f'строки с кодом {code} нет в форме — '
                                              f'правку применять некуда'})
                continue
            if _set_val(form, code, col, e['value_final']):
                applied.append({**e, 'before': cur})
            else:
                unapplied.append({**e, 'why': f'не удалось записать {code}[{col}]'})
        return {'applied': applied, 'unapplied': unapplied}

    # ─── сверка с артефактами ───

    def reconcile(self, artifacts=None):
        """Сходятся ли пометки с тем, что сейчас в артефактах.

        Это и есть «проследить изменения»: видно, что правка ещё нужна, что она устарела
        (код уже читает верное значение), что данные под пометкой поехали и её пора
        перепроверить, и что появились новые провалы правил без пометки.

        `artifacts` — {doc: артефакт}. Если не передан, читается из extracted/.
        """
        if artifacts is None:
            artifacts = {}
            for p in sorted(EXTRACTED.glob('*_6мес_*.json')):
                m = re.match(r'^(.*_6мес_\d{4})\.json$', p.name)
                if m:
                    artifacts[m.group(1)] = json.loads(p.read_text(encoding='utf-8'))

        findings = []
        for e in self.entries.values():
            art = artifacts.get(e['doc'])
            if art is None:
                findings.append({'entry': e, 'status': NO_ROW,
                                 'why': f"артефакт {e['doc']}.json не найден"})
                continue
            form = art.get(e['form'])
            if e['state'] in CLOSED_STATES:
                findings.append({'entry': e, 'status': CLOSED, 'why': 'проверка закрыта'})
                continue
            if e.get('code') is None:
                findings.append({'entry': e, 'status': ACTIVE,
                                 'why': 'спор про колонку — ждёт ручной проверки'})
                continue
            cur = _get_val(form, e['code'], e['column'])
            row_exists = any(it.get('code') == e['code'] for it in (form or {}).get('items') or [])
            if not row_exists:
                findings.append({'entry': e, 'status': NO_ROW,
                                 'why': f"строки {e['code']} нет в форме"})
            elif e['state'] == 'corrected':
                if cur == e['value_final']:
                    findings.append({'entry': e, 'status': STALE,
                                     'why': f"код уже читает {cur} — правка больше не нужна"})
                elif cur == e.get('value_read'):
                    findings.append({'entry': e, 'status': ACTIVE,
                                     'why': f"по-прежнему {cur}, правка нужна"})
                else:
                    findings.append({'entry': e, 'status': DRIFTED,
                                     'why': f"было {e.get('value_read')}, стало {cur} — "
                                            f"перепроверить правку"})
            else:  # disputed
                if cur == e.get('value_read'):
                    findings.append({'entry': e, 'status': ACTIVE,
                                     'why': 'значение не менялось — ждёт проверки'})
                else:
                    findings.append({'entry': e, 'status': DRIFTED,
                                     'why': f"было {e.get('value_read')}, стало {cur} — "
                                            f"перепроверить пометку"})
        return findings


def invisible_entries(corr, codes_in_svod):
    """Записи, которых не видно в своде: ни один их код не входит в колонки свода.

    Список кодов свода меняется реже списка отчётностей, но меняется. Запись при этом
    не теряется и остаётся в силе — она просто не даёт заливки, и спорное место тихо
    выпадает из поля зрения. Знать о таких надо, поэтому они выводятся отдельно.
    """
    out = []
    for e in corr.entries.values():
        if e['state'] in CLOSED_STATES:
            continue
        codes = [e['code']] if e.get('code') else (e.get('codes') or [])
        if codes and not any(c in codes_in_svod for c in codes):
            out.append(e)
    return out


def uncovered(corr, suspicions):
    """Из переданных спорных мест — те, на которые нет ни одной пометки.

    `suspicions` — список `(doc, form, column)` или `(doc, form, column, rule)`.
    Берётся именно результат ТРИАЖА (невязки, которые не объяснены структурой), а не
    сырые провалы правил: провал из-за строки вне родительского итога — это особенность
    разбора, а не ошибка чтения, и человеку там смотреть нечего.
    """
    out = []
    for item in suspicions:
        doc, form, column = item[0], item[1], item[2]
        rule = item[3] if len(item) > 3 else None
        if not corr.column_entries(doc, form, column):
            out.append((doc, form, column, rule))
    return out


def load_artifacts():
    arts = {}
    for p in sorted(EXTRACTED.glob('*_6мес_*.json')):
        m = re.match(r'^(.*_6мес_\d{4})\.json$', p.name)
        if m:
            arts[m.group(1)] = json.loads(p.read_text(encoding='utf-8'))
    return arts


# ─── CLI ───

def target_ru(e):
    """Человекочитаемое описание того, на что указывает запись."""
    if e.get('code'):
        return f"код {e['code']}"
    if e.get('codes'):
        return f"коды {', '.join(e['codes'])}"
    return 'вся колонка'


def _cmd_list(corr):
    c = corr.counts()
    print(f'Записей: {len(corr.entries)}  '
          f'(спорных {c["disputed"]}, правок {c["corrected"]}, '
          f'подтверждено {c["confirmed"]}, снято {c["rejected"]})')
    for e in corr.entries.values():
        tgt = (f"{e['doc']} {FORM_RU.get(e['form'], e['form'])} "
               f"кол.{e['column']} {target_ru(e)}")
        extra = ''
        if e['state'] == 'corrected':
            extra = f"  {e.get('value_read')} -> {e.get('value_final')}"
        print(f"  [{e['state']:9}] {tgt}{extra}")
        if e.get('reason'):
            print(f"              {e['reason']}")


def svod_codes():
    """Колонки свода. Импорт отложенный: svod_build сам импортирует этот модуль."""
    try:
        import svod_build
        return set(svod_build.CODES)
    except Exception:
        return set()


def _cmd_reconcile(corr):
    arts = load_artifacts()
    findings = corr.reconcile(arts)
    order = {ACTIVE: 0, DRIFTED: 1, STALE: 2, NO_ROW: 3, CLOSED: 4}
    title = {ACTIVE: 'ЖДЁТ ПРОВЕРКИ', DRIFTED: 'ДАННЫЕ ПОЕХАЛИ', STALE: 'ПРАВКА УСТАРЕЛА',
             NO_ROW: 'СТРОКИ НЕТ', CLOSED: 'ЗАКРЫТО'}
    print(f'Сверка {len(findings)} записей с артефактами:\n')
    for f in sorted(findings, key=lambda x: order[x['status']]):
        e = f['entry']
        print(f"  [{title[f['status']]:16}] {e['doc']} {e['form']} кол.{e['column']} "
              f"{target_ru(e)}: {f['why']}")

    inv = invisible_entries(corr, svod_codes())
    if inv:
        print(f'\nПометок вне колонок свода (в силе, но в своде не видны): {len(inv)}')
        for e in inv:
            print(f"  {e['doc']} {FORM_RU.get(e['form'], e['form'])} "
                  f"кол.{e['column']}: {target_ru(e)}")

    bad = [f for f in findings if f['status'] in (DRIFTED, STALE, NO_ROW)]
    print('\nСверку пометок с триажем невязок делает _verify_artifacts.py '
          '(он знает, какая невязка объяснена структурой, а какая — нет).')
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list', action='store_true', help='показать записи')
    ap.add_argument('--reconcile', action='store_true', help='сверить с артефактами')
    ap.add_argument('--mark', nargs=3, metavar=('DOC', 'FORM', 'COLUMN'),
                    help='пометить ячейку или колонку')
    ap.add_argument('--code', default=None, help='код строки (для --mark)')
    ap.add_argument('--codes', default=None,
                    help='список подозреваемых кодов через запятую (для спора про колонку)')
    ap.add_argument('--rule', default=None, help='правило, из-за которого спор (для --mark)')
    ap.add_argument('--state', default='disputed', choices=STATES)
    ap.add_argument('--value-final', type=int, default=None, help='верное значение')
    ap.add_argument('--value-read', type=int, default=None, help='что прочитала модель')
    ap.add_argument('--reason', default='')
    ap.add_argument('--path', default=str(CORRECTIONS_PATH))
    args = ap.parse_args(argv)

    corr = Corrections.load(args.path)

    if args.mark:
        doc, form, col = args.mark
        corr.record(doc, form, int(col),
                    code=args.code,
                    codes=[c.strip() for c in args.codes.split(',')] if args.codes else None,
                    rule=args.rule, state=args.state,
                    value_read=args.value_read, value_final=args.value_final,
                    reason=args.reason, source='human')
        corr.save()
        print(f'записано; всего записей {len(corr.entries)}')
        return 0

    if args.reconcile:
        return _cmd_reconcile(corr)

    _cmd_list(corr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
