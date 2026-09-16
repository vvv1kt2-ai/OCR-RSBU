# -*- coding: utf-8 -*-
r"""ПРАВКА «Моторные технологии_6мес_2025»: вернуть 5 затёртых эскалацией ячеек колонки 0.

Основание (доказано, не предположено):
  1) транскрипт страницы 2 (и gemini 200 dpi, и claude 300 dpi, у обоих поставщиков) печатает
     ровно те же числа: 1220=457, 1230=200 346, 1250=4 070, 1260=467, 1200=459 962;
  2) values_ocr1 содержит ИМЕННО эти числа;
  3) независимая арифметика артефакта: 1600-1100 = 459962 / 481336 / 377952 совпадает с
     values_ocr1(1200) во ВСЕХ трёх колонках.

Правим ТОЛЬКО values. Поля checks/status не трогаем (политика проекта: проверки не подгонять
под данные). status останется needs_review — и это верно: у документа есть отдельный остаток
раздела II (пропущена вторая строка 1250 «Депозитные счета» = 14 500), её эта правка не лечит.

Порядок: бэкап -> журнал -> правка -> самопроверка. Идемпотентно: повторный запуск ничего не
меняет (затёртых ячеек уже нет).
"""
import io, json, os, shutil, hashlib, datetime

EX = r'D:\models\extracted'
STEM = 'Моторные технологии_6мес_2025'
SRC = os.path.join(EX, STEM + '.json')
BAK_DIR = os.path.join(EX, '_backup_motor_2025')
LOG = os.path.join(EX, '_fix_motor_log.json')
SVOD_CSV = os.path.join(EX, 'svod_2025_2026.csv')
SVOD_XLSX = os.path.join(EX, 'svod_2025_2026.xlsx')
EXPECT_CSV = 'A64C4C31B41B'

DRY = os.environ.get('MOTOR_APPLY') != '1'


def sha(p):
    return hashlib.sha1(io.open(p, 'rb').read()).hexdigest()[:12].upper()


print('режим: %s' % ('СУХОЙ ПРОГОН (ничего не пишется)' if DRY else 'ПРИМЕНЕНИЕ ПРАВКИ'))
print('свод до: csv=%s  xlsx=%s' % (sha(SVOD_CSV), sha(SVOD_XLSX)))

j = json.load(io.open(SRC, encoding='utf-8'))
items = ((j.get('balance') or {}).get('items')) or []

todo = []
for it in items:
    c = str(it.get('code') or '')
    v = list(it.get('values') or [])
    o = it.get('values_ocr1') or []
    if not v or not o:
        continue
    for k in range(min(len(v), len(o))):
        a, b = v[k], o[k]
        if (a in ('', None)) and (b not in ('', None)):
            todo.append((c, k, b, it.get('name')))

print('\nячеек к правке: %d' % len(todo))
for c, k, b, name in todo:
    print('   %-6s кол.%d  "" -> %-10s (%s)' % (c, k, b, (name or '')[:40]))

if not todo:
    print('\nнечего править — документ уже в целевом состоянии (идемпотентно)')
    raise SystemExit(0)

if DRY:
    print('\nсухой прогон: файлы не изменены. Для применения: MOTOR_APPLY=1')
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
for it in items:
    c = str(it.get('code') or '')
    v = list(it.get('values') or [])
    o = it.get('values_ocr1') or []
    if not v or not o:
        continue
    changed = False
    for k in range(min(len(v), len(o))):
        if (v[k] in ('', None)) and (o[k] not in ('', None)):
            v[k] = o[k]
            changed = True
    if changed:
        it['values'] = v

j.setdefault('warnings', []).append(
    'ПРАВКА 16.09.2026: восстановлены 5 ячеек колонки 0 (1200/1220/1230/1250/1260), '
    'затёртых эскалацией; значения взяты из values_ocr1 и подтверждены транскриптом стр. 2 '
    'и арифметикой 1600-1100. checks/status не пересчитывались.')
j['fixed_at'] = datetime.datetime.now().isoformat(timespec='seconds')

tmp = SRC + '.tmp'
with io.open(tmp, 'w', encoding='utf-8') as f:
    json.dump(j, f, ensure_ascii=False, indent=1)
os.replace(tmp, SRC)
print('записано: %s (sha1 %s)' % (SRC, sha(SRC)))

# --- журнал
entry = {
    'document': STEM, 'date': datetime.datetime.now().isoformat(timespec='seconds'),
    'reason': 'эскалация вернула пустой столбец 0; values_ocr1 держал верные значения',
    'basis': ['транскрипт p2: 1220=457 1230=200346 1250=4070 1260=467 1200=459962',
              'арифметика артефакта: 1600-1100 = values_ocr1(1200) во всех трёх колонках'],
    'backup': os.path.relpath(bak, r'D:\models'),
    'cells': [{'code': c, 'col': k, 'value': b} for c, k, b, _ in todo],
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
left = sum(1 for it in ((j2.get('balance') or {}).get('items') or [])
           for k in range(len(it.get('values') or []))
           if k < len(it.get('values_ocr1') or [])
           and (it['values'][k] in ('', None)) and (it['values_ocr1'][k] not in ('', None)))
print('осталось затёртых ячеек: %d' % left)

print('свод после: csv=%s  xlsx=%s  -> %s'
      % (sha(SVOD_CSV), sha(SVOD_XLSX),
         'НЕ ИЗМЕНИЛСЯ' if sha(SVOD_CSV) == EXPECT_CSV else 'ВНИМАНИЕ, изменился!'))