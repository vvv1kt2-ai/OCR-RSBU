# -*- coding: utf-8 -*-
r"""Тест выбора модели по стоимости: разбор прайса, профиль токенов, арифметика.

Проверяется то, из-за чего инструмент может соврать:

1. Разбор прайса. Строки-разделители групп («━━━ claude-sonnet-5 ━━━») не должны
   становиться вариантами, а цены вида «4,72» (запятая) — читаться как числа.
2. Профиль токенов. Роль определяется по БАЗОВОМУ имени модели: в журнале адрес записан
   без вендорного префикса и с хвостом варианта, поэтому `claude-sonnet-5.5` не должен
   попасть в роль `claude-sonnet-5`.
3. Арифметика. Ранг обязан считаться по профилю роли, а не по цене за миллион: при 8%
   выхода дешёвый выход почти не помогает, при 73% — решает.

Без сети и без записи в рабочие файлы: прайс и журнал создаются во временном каталоге.
Запуск: python D:\models\tests\test_choose_model.py
Лог:    tests\_last_run_choose_model.txt
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, r'D:\models')
import choose_model as C

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_choose_model.txt'), 'w',
              encoding='utf-8')
ok = fail = 0


def check(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        LOG.write(f'  OK   {name}\n')
    else:
        fail += 1
        LOG.write(f'  ПРОВАЛ {name} {detail}\n')


# ─── 1. базовое имя модели ───
check('base_name убирает вендора', C.base_name('anthropic/claude-sonnet-5') == 'claude-sonnet-5')
check('base_name убирает вариант', C.base_name('anthropic/claude-sonnet-5:cxc2') == 'claude-sonnet-5')
check('base_name убирает и то и другое', C.base_name('z-ai/glm-5.2:yellow') == 'glm-5.2')
check('base_name не путает 5 и 5.5',
      C.base_name('claude-sonnet-5.5') != C.base_name('anthropic/claude-sonnet-5'))
check('base_name на пустом не падает', C.base_name(None) == '')

# ─── 2. числа из прайса ───
check('запятая как разделитель', C._num('4,72') == 4.72)
check('точка как разделитель', C._num('4.72') == 4.72)
check('пробел внутри числа', C._num('1 234,50') == 1234.5)
check('пустое -> None', C._num('') is None and C._num(None) is None)
check('мусор -> None', C._num('—') is None)

# ─── 3. разбор прайса ───
tmp = tempfile.mkdtemp(prefix='choose_model_')
xlsx = os.path.join(tmp, 'prices.xlsx')
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.append(['Цены актуальны на 2026-11-24. Цены в ₽ за 1 000 000 токенов.'])
ws.append(['Модель', 'Производитель', 'Вариант', 'model (для API)',
           'Вход, ₽/1М', 'Выход, ₽/1М'])
ws.append(['━━━━━━━━━━ test-model ━━━━━━━━━━'])
ws.append(['test-model', 'Test', 'Base · по умолчанию', 'test-model', '10,00', '100,00'])
ws.append(['test-model', 'Test', 'Cheap', 'test-model:cheap', '12,00', '20,00'])
ws.append([])
ws.append(['━━━━━━━━━━ other-model ━━━━━━━━━━'])
ws.append(['other-model', 'Test', 'Base', 'other-model', 1, 2])
wb.save(xlsx)
wb.close()

rows, stamp = C.parse_prices(xlsx)
check('прайс: дата снятия прочитана', '2026-11-24' in (stamp or ''), stamp)
check('прайс: разделители групп не стали вариантами',
      all(not r[3].startswith('━') for r in rows), [r[3] for r in rows])
check('прайс: два варианта + второй модели = 3 строки', len(rows) == 3, len(rows))
check('прайс: группа подписана у варианта',
      any(r[0] == 'test-model' and r[3] == 'test-model:cheap' for r in rows), rows)
check('прайс: цена с запятой разобрана',
      any(r[3] == 'test-model' and r[4] == 10.0 and r[5] == 100.0 for r in rows), rows)

# ─── 4. профиль токенов из журнала ───
ndjson = os.path.join(tmp, 'usage.ndjson')
with io.open(ndjson, 'w', encoding='utf-8') as f:
    for rec in ({'model': 'test-model:cheap', 'prompt_tokens': 100, 'completion_tokens': 900},
                {'model': 'test-model', 'prompt_tokens': 300, 'completion_tokens': 100},
                {'model': 'test-model-extra', 'prompt_tokens': 999, 'completion_tokens': 999}):
        f.write(json.dumps(rec) + '\n')
prof = C.token_profile(ndjson, {'main': 'test-model'})
check('журнал: роль найдена по базовому имени', 'main' in prof, prof)
check('журнал: чужая модель не приписана роли (test-model-extra)',
      prof.get('main', (0, 0, 0))[2] == 2, prof)
check('журнал: средние считаются по вызовам',
      prof['main'][0] == 200.0 and prof['main'][1] == 500.0, prof)

# ─── 5. арифметика и ранг ───
check('стоимость 1000 вызовов при 0 токенов = 0',
      C.cost_per_calls(10, 100, 0, 0, 1000) == 0)
check('стоимость: только вход',
      abs(C.cost_per_calls(10, 100, 1_000_000, 0, 1) - 10) < 1e-9)
check('стоимость: только выход',
      abs(C.cost_per_calls(10, 100, 0, 1_000_000, 1) - 100) < 1e-9)
check('стоимость: неизвестная цена -> None', C.cost_per_calls(None, 5, 1, 1) is None)

# входная роль (8% выхода): «дешёвый вход» выигрывает
in_heavy = (C.cost_per_calls(10, 100, 14918, 1243), C.cost_per_calls(12, 20, 14918, 1243))
check('входная роль: дорогой выход проигрывает при дешёвом входе',
      in_heavy[1] < in_heavy[0], in_heavy)
# выходная роль (73% выхода): дешёвый выход выигрывает, хотя вход дороже
out_heavy = (C.cost_per_calls(10, 100, 1181, 3211), C.cost_per_calls(12, 20, 1181, 3211))
check('выходная роль: дешёвый выход выигрывает даже при дорогом входе',
      out_heavy[1] < out_heavy[0], out_heavy)

# ─── 6. устойчивость ранга к профилю ───
# Профиль не константа: доля выхода у detect в журнале 1…90%. Внутри одной модели дешёвый
# вариант дешевле по обеим осям, и ранг не меняется; у разных моделей — может.
same_model = [('g', 'V', 'base', 'm', 10.0, 100.0), ('g', 'V', 'cheap', 'm:cheap', 8.0, 80.0)]
lo = C.cheapest_at_share(same_model, 10_000, 0.05, 1)
hi = C.cheapest_at_share(same_model, 10_000, 0.95, 1)
check('ранг внутри модели не зависит от профиля', lo[1] == hi[1] == 'm:cheap', (lo, hi))

mixed = [('g', 'V', 'cheap_in', 'a', 1.0, 50.0), ('g', 'V', 'cheap_out', 'b', 10.0, 5.0)]
lo2 = C.cheapest_at_share(mixed, 10_000, 0.05, 1)
hi2 = C.cheapest_at_share(mixed, 10_000, 0.95, 1)
check('у разных моделей ранг переворачивается', lo2[1] == 'a' and hi2[1] == 'b', (lo2, hi2))
check('cheapest_at_share отдаёт стоимость, а не только адрес',
      lo2[0] > 0 and isinstance(lo2[1], str), lo2)

# ─── 7. разброс профиля ───
nd2 = os.path.join(tmp, 'spread.ndjson')
with io.open(nd2, 'w', encoding='utf-8') as f:
    for pt, ct in ((100, 900), (500, 500), (900, 100), (1000, 0)):
        f.write(json.dumps({'model': 'test-model', 'prompt_tokens': pt,
                            'completion_tokens': ct}) + '\n')
sp = C.share_spread(nd2, {'main': 'test-model'})
check('разброс: диапазон доли выхода посчитан', 'main' in sp, sp)
check('разброс: p10 меньше p90', sp['main'][0] < sp['main'][1], sp)
check('разброс: пустой журнал не падает', C.share_spread(os.path.join(tmp, 'нет.ndjson'),
                                                          {'main': 'x'}) == {})

# ─── 8. реальный прайс, если он на месте ───
real = r'C:\Users\1\Downloads\Книга3.xlsx'
if os.path.exists(real):
    rr, st = C.parse_prices(real)
    check('реальный прайс: строк с адресом больше 400', len(rr) > 400, len(rr))
    addrs = {r[3] for r in rr}
    check('реальный прайс: адрес роли esc на месте', 'anthropic/claude-sonnet-5' in addrs)
    check('реальный прайс: варианты esc присутствуют',
          any(a.startswith('anthropic/claude-sonnet-5:') for a in addrs))
else:
    LOG.write('  (прайс Книга3.xlsx отсутствует — проверки на реальном файле пропущены)\n')

LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
LOG.close()
print(f'успешно {ok}, провалов {fail} (лог: tests/_last_run_choose_model.txt)')
sys.exit(1 if fail else 0)
