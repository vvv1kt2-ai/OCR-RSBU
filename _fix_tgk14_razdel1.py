# -*- coding: utf-8 -*-
r"""ПРАВКА «ТГК-14_6мес_2025»: вернуть раздел I, переписанный эскалацией.

Основание (доказано, не предположено):
  1) транскрипт стр. 3 на 200 dpi — у ОБОИХ поставщиков и побайтово одинаково — печатает:
     1110 = 755 060 | 1150 = 14 702 617 | 1160 = «-» | 1170 = 2 710 153 / 2 289 999 / 3 374 497
     1180 = 234 303 | 1190 = 3 160 463 | 1100 = 21 562 596 / 18 728 281 / 16 841 188;
  2) values_ocr1 держит ИМЕННО эти числа, а действующие values — результат транскрипта 300 dpi
     от plusvibe, в котором строка 1170 уехала в 1160, а в 1170 встало другое число;
  3) арифметика подтверждает values_ocr1: 755060+14702617+2710153+234303+3160463 = 21562596
     совпадает с 1100 кол.0 ТОЧНО; кол.1 сходится точно так же (18728281); кол.2 расходится
     на 10 — и ровно на последнюю цифру 1170 (…497 против …487 у транскрипта 300 dpi).

Правим ТОЛЬКО values. Поля checks/status не трогаем (политика проекта: проверки не подгонять
под данные). Идемпотентно: повторный запуск ничего не меняет.

Открытый вопрос, который эта правка НЕ решает и решать не должна: последняя цифра 1170 кол.2.
Арифметика говорит 3 374 487, транскрипт 200 dpi — 3 374 497. Ставить 487 «по арифметике»
нельзя: это уже выбор значения, а не откат. Нужно третье чтение — но не сейчас.
"""
import io, json, os, shutil, hashlib, datetime

EX = r'D:\models\extracted'
STEM = 'ТГК-14_6мес_2025'
SRC = os.path.join(EX, STEM + '.json')
BAK_DIR = os.path.join(EX, '_backup_tgk14_2025')
LOG = os.path.join(EX, '_fix_tgk14_log.json')
SVOD_CSV = os.path.join(EX, 'svod_2025_2026.csv')
SVOD_XLSX = os.path.join(EX, 'svod_2025_2026.xlsx')
EXPECT_CSV = 'A64C4C31B41B'

DRY = os.environ.get('TGK14_APPLY') != '1'


def sha(p):
    return hashlib.sha1(io.open(p, 'rb').read()).hexdigest()[:12].upper()


print('режим: %s' % ('СУХОЙ ПРОГОН (ничего не пишется)' if DRY else 'ПРИМЕНЕНИЕ ПРАВКИ'))
print('свод до: csv=%s  xlsx=%s' % (sha(SVOD_CSV), sha(SVOD_XLSX)))

j = json.load(io.open(SRC, encoding='utf-8'))

todo = []
for fk in ('balance', 'income_statement', 'cash_flow'):
    for it in ((j.get(fk) or {}).get('items') or []):
        for tgt in [it] + list(it.get('children') or []):
            o = tgt.get('values_ocr1')
            if o is None:
                continue
            v = tgt.get('values') or []
            for k in range(min(len(v), len(o))):
                if v[k] != o[k]:
                    todo.append((fk, str(tgt.get('code') or ''), k, v[k], o[k],
                                 tgt.get('name')))

print('\nячеек к правке: %d' % len(todo))
for fk, c, k, was, now, name in todo:
    print('   %-6s кол.%d  %-12s -> %-12s (%s)' % (c, k, was, now, (name or '')[:34]))

if not todo:
    print('\nнечего править — документ уже в целевом состоянии (идемпотентно)')
    raise SystemExit(0)

if DRY:
    print('\nсухой прогон: файлы не изменены. Для применения: TGK14_APPLY=1')
    raise SystemExit(0)

# --- бэкап
os.makedirs(BAK_DIR, exist_ok=True)
bak = os.path.join(BAK_DIR, STEM + '.json')
if not os.path.exists(bak):
    shutil.copy2(SRC, bak)
    print('\nбэкап: %s (sha1 %s)' % (bak, sha(bak)))
else:
    print('\nбэкап уже есть: %s (sha1 %s) — не перезаписываю' % (bak, sha(bak)))

# --- правка
n = 0
for fk in ('balance', 'income_statement', 'cash_flow'):
    for it in ((j.get(fk) or {}).get('items') or []):
        for tgt in [it] + list(it.get('children') or []):
            o = tgt.get('values_ocr1')
            if o is None:
                continue
            v = list(tgt.get('values') or [])
            changed = False
            for k in range(min(len(v), len(o))):
                if v[k] != o[k]:
                    v[k] = o[k]
                    changed = True
            if changed:
                tgt['values'] = v
                n += 1

j.setdefault('warnings', []).append(
    'ПРАВКА 16.09.2026: раздел I возвращён из values_ocr1 (5 строк: 1110/1160/1170/1180/1100). '
    'Эскалация 300 dpi переписала его хуже: значение 1170 уехало в 1160, в 1170 встало другое '
    'число, невязка раздела выросла с 10 до 6 367 368. Основание — оба транскрипта 200 dpi '
    '(совпадают побайтово) плюс арифметика: 755060+14702617+2710153+234303+3160463 = 21562596 '
    '= 1100 кол.0 точно. checks/status не пересчитывались.')
j['fixed_at'] = datetime.datetime.now().isoformat(timespec='seconds')

tmp = SRC + '.tmp'
with io.open(tmp, 'w', encoding='utf-8') as f:
    json.dump(j, f, ensure_ascii=False, indent=1)
os.replace(tmp, SRC)
print('записано: %s (sha1 %s), изменено строк: %d' % (SRC, sha(SRC), n))

# --- журнал
entry = {
    'document': STEM, 'date': datetime.datetime.now().isoformat(timespec='seconds'),
    'reason': 'эскалация 300 dpi переписала раздел I: значение 1170 уехало в 1160',
    'basis': ['транскрипт стр.3 200 dpi (polza и plusvibe, идентичны): 1160 = «-», '
              '1170 = 2710153/2289999/3374497, 1110 = 755060, 1180 = 234303, '
              '1100 = 21562596/18728281/16841188',
              'арифметика: 755060+14702617+2710153+234303+3160463 = 21562596 = 1100 кол.0 точно; '
              'кол.1 сходится точно; кол.2 расходится на 10 (последняя цифра 1170)'],
    'open_question': 'последняя цифра 1170 кол.2: арифметика даёт 3 374 487, транскрипт 200 dpi '
                     '3 374 497; нужно третье чтение, правкой не решается',
    'backup': os.path.relpath(bak, r'D:\models'),
    'cells': [{'form': fk, 'code': c, 'col': k, 'was': was, 'now': now}
              for fk, c, k, was, now, _ in todo],
}
hist = []
if os.path.exists(LOG):
    try:
        hist = json.load(io.open(LOG, encoding='utf-8'))
    except Exception:
        hist = []
hist.append(entry)
with io.open(LOG, 'w', encoding='utf-8') as f:
    json.dump(hist, f, ensure_ascii=False, indent=1)
print('журнал: %s (записей %d)' % (LOG, len(hist)))

# --- самопроверка
j2 = json.load(io.open(SRC, encoding='utf-8'))
left = 0
for fk in ('balance', 'income_statement', 'cash_flow'):
    for it in ((j2.get(fk) or {}).get('items') or []):
        for tgt in [it] + list(it.get('children') or []):
            o = tgt.get('values_ocr1')
            if o is None:
                continue
            v = tgt.get('values') or []
            left += sum(1 for k in range(min(len(v), len(o))) if v[k] != o[k])
print('осталось расхождений с values_ocr1: %d' % left)

print('свод после: csv=%s  xlsx=%s  -> %s'
      % (sha(SVOD_CSV), sha(SVOD_XLSX),
         'НЕ ИЗМЕНИЛСЯ' if sha(SVOD_CSV) == EXPECT_CSV else 'ВНИМАНИЕ, изменился!'))
