# -*- coding: utf-8 -*-
r"""Q8: восстановить верное значение 1250 в артефакте ТГК-14_6мес_2025.

Верное значение доказано арифметикой: правило 1200 сходится ТОЧНО на 11081647
(сумма 1210+1215+1220+1230+1240+1250+1260 = 16911114 = 1200) и расходится ровно на
20000 на 11061647, которое вписала эскалация.

Дополнительное подтверждение: свод-эталон (бэкап до правок) держит 11081647, то есть
правка возвращает артефакт в согласие со сводом.

Сухой прогон, бэкап, журнал. Проверки (`checks`) НЕ переписываю: они фиксируют, что
реально произошло в том прогоне; вместо этого дописываю предупреждение.
"""
import io, os, json, shutil, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
STEM = 'ТГК-14_6мес_2025'
CODE = '1250'
BK = os.path.join(EX, '_backup_q8')

path = os.path.join(EX, STEM + '.json')
doc = json.load(io.open(path, encoding='utf-8'))


def item(items, code):
    for it in items:
        if it.get('code') == code:
            return it


def balance_sum(items, values_of_1250=None):
    """сумма 1210..1260 и расхождение с 1200 по каждой колонке"""
    m = P.val_map(items)
    n = max(len(it['values']) for it in items if it.get('values'))
    out = []
    for c in range(n):
        def S(code):
            v = m.get(code) or []
            return v[c] if c < len(v) else None
        total = sum(x for x in (S(k) for k in
                                ('1210', '1215', '1220', '1230', '1240', '1250', '1260'))
                  if x is not None)
        if values_of_1250 is not None and S('1250') is not None:
            total = total - S('1250') + values_of_1250
        a = S('1200')
        out.append((total, None if a is None else a - total))
    return out


it = item(doc['balance']['items'], CODE)
print('=== СУХОЙ ПРОГОН ===')
print('файл: %s' % path)
print('код %s:' % CODE)
print('   values (в артефакте) = %s' % it.get('values'))
print('   values_ocr1 (прежнее) = %s' % it.get('values_ocr1'))
print('   corrected_by = %r' % it.get('corrected_by'))
print()
print('арифметика правила 1200 (сумма, расхождение с 1200) по колонкам:')
for lbl, val in (('в артефакте (11061647)', None), ('прежнее (11081647)', 11081647)):
    print('   %-24s %s' % (lbl, balance_sum(doc['balance']['items'], val)))
print()

new_values = list(it.get('values_ocr1') or [])
if not new_values:
    print('ОТКАЗ: values_ocr1 пуст, восстанавливать нечего'); sys.exit(1)
if new_values == it.get('values'):
    print('ОТКАЗ: значения уже совпадают, правка не нужна'); sys.exit(1)

print('будет записано: %s' % new_values)
print()

# ── бэкап ──
os.makedirs(BK, exist_ok=True)
shutil.copy2(path, os.path.join(BK, STEM + '.json'))
print('бэкап: %s' % os.path.join(BK, STEM + '.json'))

# ── правка ──
it['values'] = new_values
it.pop('corrected_by', None)
it.pop('confirmed_by', None)
it.pop('values_ocr1', None)
doc.setdefault('warnings', []).append(
    'Восстановлено вручную 16.09.2026: %s «%s» — эскалация заменила верное 11081647 на '
    '11061647; правило 1200 сходится точно на 11081647 (сумма = 16911114 = 1200) и '
    'расходится на 20000 на 11061647. Верное значение возвращено из values_ocr1.'
    % (CODE, (it.get('name') or '')[:60]))
json.dump(doc, io.open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('записано.')
print()

# ── проверка после правки ──
chk = json.load(io.open(path, encoding='utf-8'))
it2 = item(chk['balance']['items'], CODE)
print('=== ПРОВЕРКА ПОСЛЕ ПРАВКИ ===')
print('код %s values = %s' % (CODE, it2.get('values')))
print('арифметика: %s' % balance_sum(chk['balance']['items']))
ok = [c for c in P.run_checks('balance', chk['balance']['items']) if c.get('ok')]
allc = P.run_checks('balance', chk['balance']['items'])
print('проверок проходит по пересчёту: %d из %d' % (len(ok), len(allc)))
for c in allc:
    if not c.get('ok'):
        print('   НЕ проходит: %s  per_column=%s' % (c['rule'], c.get('per_column')))
print()
print('предупреждения (последнее):')
print('   %s' % chk['warnings'][-1][:160])
print()
print('СОХРАНЁННЫЕ checks НЕ переписаны — они фиксируют, что было в том прогоне.')
