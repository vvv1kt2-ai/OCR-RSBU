# -*- coding: utf-8 -*-
r"""Складывать дубль или нет? Решает АРИФМЕТИКА раздела, а не форма строки.

Проверка, которая не даёт ошибиться: для каждого документа с дублем кода считаем итог раздела
двумя способами — как сейчАС (взят один из дублей) и СО СЛОЖЕНИЕМ дублей. Правильным считаем тот,
при котором тождество раздела выполняется:

  раздел II  (оборотные активы): 1200 = 1210+1215+1220+1230+1240+1250+1260
  раздел V   (краткосрочные):    1500 = 1510+1520+1530+1540+1550
  раздел IV  (долгосрочные):     1400 = 1410+1420+1430+1450
  раздел I:                     1100 = 1110+1150+1160+1170+1180+1190
  баланс:                       1600 = 1100+1200

Если сумма сходится ТОЛЬКО со сложением — складывать надо (дубль это отдельная строка отчёта).
Если сходится ТОЛЬКО без — складывать НЕЛЬЗЯ (дубль это повтор кода у дочерней строки).
Если сходится и так и так — случай пустой (второй дубль нулевой), складывать безвредно.
"""
import io, os, re, glob, collections

PAGES = r'D:\models\extracted\pages'
CELL = re.compile(r'\|\s*(\d{4})\s*\|')
# строка таблицы: | имя | код | зн1 | зн2 | зн3 |
ROW = re.compile(r'^\s*\|(?P<cells>.+)\|\s*$')

SECTIONS = {
    '1100': ['1110', '1150', '1160', '1170', '1180', '1190'],
    '1200': ['1210', '1215', '1220', '1230', '1240', '1250', '1260'],
    '1400': ['1410', '1420', '1430', '1450'],
    '1500': ['1510', '1520', '1530', '1540', '1550'],
}


def num(x):
    x = (x or '').replace('\u00a0', ' ').strip()
    if x in ('', '-', '—', '–'):
        return None
    neg = x.startswith('(') and x.endswith(')')
    d = re.sub(r'[^\d,.\-]', '', x).strip('()').replace(' ', '').replace(',', '.')
    if not d:
        return None
    try:
        return (-1 if neg else 1) * float(d)
    except ValueError:
        return None


def parse(path):
    """вернуть список (код, имя, [значения]) и словарь код -> список вхождений"""
    rows = []
    for ln in io.open(path, encoding='utf-8', errors='replace').read().splitlines():
        m = ROW.match(ln)
        if not m:
            continue
        cells = [c.strip() for c in m.group('cells').split('|')]
        if len(cells) < 3:
            continue
        code_i = None
        for i, c in enumerate(cells):
            if re.fullmatch(r'\d{4}', c):
                code_i = i
                break
        if code_i is None:
            continue
        code = cells[code_i]
        name = ' '.join(cells[:code_i]).strip(' *')
        vals = cells[code_i + 1:]
        rows.append((code, name, vals))
    occ = collections.defaultdict(list)
    for r in rows:
        occ[r[0]].append(r)
    return rows, occ


def total(occ, code, col, mode='first'):
    """значение итогового кода: first (как сейчас) или sum (со сложением дублей)"""
    rs = occ.get(code) or []
    if not rs:
        return None
    if mode == 'first':
        v = rs[0][2][col] if col < len(rs[0][2]) else ''
        return num(v)
    s, any_ = 0.0, False
    for r in rs:
        v = num(r[2][col]) if col < len(r[2]) else None
        if v is not None:
            s += v
            any_ = True
    return s if any_ else None


best = {}
for f in glob.glob(os.path.join(PAGES, '*_p*_200_*.md')):
    b = os.path.basename(f)
    m = re.match(r'^(?P<doc>.+)_p(?P<page>\d+)_200_.*\.md$', b)
    if m:
        best.setdefault((m.group('doc'), int(m.group('page'))), f)

print('%-34s %-5s %-6s %-22s %s' % ('документ', 'стр', 'код', 'дубль (имя=значения)', 'итог раздела: сейчас / со сложением'))
print('-' * 130)
verdict = collections.Counter()
for (doc, page), f in sorted(best.items()):
    rows, occ = parse(f)
    # рассматриваем дубли только тех кодов, что входят в тождества
    interesting = {c for sec in SECTIONS.values() for c in sec}
    dups = {c: rs for c, rs in occ.items() if len(rs) >= 2 and c in interesting}
    if not dups:
        continue
    for code, rs in sorted(dups.items()):
        # раздел, куда входит код
        for tot, parts in SECTIONS.items():
            if code not in parts:
                continue
            for col in range(3):
                t = total(occ, tot, col, 'first')
                a_f = sum(x for x in (total(occ, p, col, 'first') for p in parts) if x is not None)
                a_s = sum(x for x in (total(occ, p, col, 'sum') for p in parts) if x is not None)
                if t is None:
                    continue
                ok_f = abs(t - a_f) < 1
                ok_s = abs(t - a_s) < 1
                if ok_f == ok_s:
                    continue          # ничего не решает
                verdict['складывать' if ok_s else 'НЕ складывать'] += 1
                names = '; '.join('%s=%s' % (r[1][:22] or '-', r[2][col] if col < len(r[2]) else '')
                                  for r in rs)
                print('%-34s %-5d %-6s кол.%d %-22s %s -> %s'
                      % (doc[:34], page, code, col, names[:22],
                         '%s / %s' % ('%g' % a_f, '%g' % a_s),
                         'СО СЛОЖЕНИЕМ ОК' if ok_s else 'БЕЗ сложения ОК'))
                break
print('-' * 130)
print('итог: %s' % dict(verdict))
