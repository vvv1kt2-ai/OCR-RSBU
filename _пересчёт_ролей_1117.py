# -*- coding: utf-8 -*-
r"""Пересчёт ролей по прайсу PlusVibe 17.11.2026.

Опора — измеренные токены пилота (не оценки):
    main   923 532 вх / 2 812 801 вых (514 вызовов)
    esc    401 575 вх /   162 299 вых (84 вызова)
    detect 251 059 вх /     8 683 вых (61 вызов)
Плюс замер 02.11.2026 на новых отчётах: 0.055 ₽ за страницу при текущей конфигурации.

Считаются три вещи:
  1. что стало с ценами наших моделей с 30.10 по 17.11;
  2. сколько стоит пилот и 135 эмитентов на каждой модели-кандидате в каждой роли;
  3. какие каналы (варианты) живы и чем отличаются — цена варианта у одной модели
     различается в 5-10 раз, поэтому «модель» без варианта не выбирают.

Запуск: python _пересчёт_ролей_1117.py
"""
import json, os

M = 1_000_000.0
TOK = {
    'main':   (923_532, 2_812_801, 514),
    'esc':    (401_575,   162_299,  84),
    'detect': (251_059,     8_683,  61),
}
REASONING_CUT = 0.74
SCALE135 = 135 / 41.0

HERE = os.path.dirname(os.path.abspath(__file__))
PRICES = os.path.join(HERE, 'модели и цены', '_pv_prices_1117.json')
OLD = os.path.join(HERE, 'модели и цены', '_pv_prices_xlsx.json')

# кандидаты: (метка, адрес модели в прайсе, зачем смотрим)
CANDS = {
    'main': [
        ('сейчас', 'google/gemini-3.8-flash'),
        ('OpenAI luna', 'openai/gpt-5.6-luna'),
        ('OpenAI luna purple', 'gpt-6-luna:purple'),
        ('OpenAI terra', 'gpt-6.1-terra:purple'),
        ('OpenAI sol', 'gpt-6.1-sol:cx'),
        ('DeepSeek', 'deepseek-v4.1-flash'),
        ('Sonnet 5.5', 'claude-sonnet-5.5:cxc'),
    ],
    'esc': [
        ('сейчас (мёртв)', 'anthropic/claude-sonnet-5:network'),
        ('Sonnet 5 cxc', 'anthropic/claude-sonnet-5:cxc'),
        ('Sonnet 5.5 cxc', 'claude-sonnet-5.5:cxc'),
        ('OpenAI sol', 'gpt-6.1-sol:cx'),
        ('OpenAI sol 5.6', 'openai/gpt-5.6-sol'),
        ('OpenAI terra', 'gpt-6.1-terra:purple'),
        ('Haiku 5.5', 'claude-haiku-5.5:cxc'),
        ('DeepSeek', 'deepseek-v4.1-flash'),
    ],
    'detect': [
        ('сейчас', 'deepseek-v4.1-flash'),
        ('OpenAI luna purple', 'gpt-6-luna:purple'),
        ('OpenAI luna', 'openai/gpt-5.6-luna'),
        ('GLM flash', 'z-ai/glm-5.3-flash:network'),
    ],
}


def load(path):
    recs = json.load(open(path, encoding='utf-8'))
    out = {}
    for r in recs:
        addr = r.get('model (для API)') or ''
        if not addr:
            continue
        try:
            inp = float(str(r.get('Вход, ₽/1М')).replace(' ', '').replace(',', '.'))
            outp = float(str(r.get('Выход, ₽/1М')).replace(' ', '').replace(',', '.'))
        except (TypeError, ValueError):
            continue
        out[addr] = dict(inp=inp, out=outp, variant=r.get('Вариант', ''),
                         vision=r.get('Vision') == 'да',
                         reasoning=r.get('Reasoning') == 'да',
                         ctx=r.get('Контекст, ток.'), maxout=r.get('Макс. вывод, ток.'),
                         vendor=r.get('Производитель', ''))
    return out


def cost(role, p, reasoning_off=False):
    pin, pout, _ = TOK[role]
    scale = (1 - REASONING_CUT) if (reasoning_off and role == 'main') else 1.0
    return (pin * p['inp'] + pout * scale * p['out']) / M


def main():
    new, old = load(PRICES), load(OLD)
    print('=== 1. ЧТО СТАЛО С ЦЕНАМИ (₽ за 1 млн, вход/выход) ===')
    print(f'{"адрес":<44}{"30.10":>16}{"17.11":>16}{"изменение":>12}')
    for addr in ('google/gemini-3.8-flash', 'deepseek-v4.1-flash',
                 'anthropic/claude-sonnet-5:cxc', 'anthropic/claude-sonnet-5:network',
                 'claude-haiku-5.5', 'claude-sonnet-5.5:cxc'):
        a, b = old.get(addr), new.get(addr)
        if not b:
            print(f'{addr:<44}{"%.2f/%.2f" % (a["inp"], a["out"]) if a else "—":>16}'
                  f'{"НЕТ В ПРАЙСЕ":>16}')
            continue
        sa = f'{a["inp"]:.2f}/{a["out"]:.2f}' if a else '—'
        sb = f'{b["inp"]:.2f}/{b["out"]:.2f}'
        ch = f'×{a["inp"] / b["inp"]:.2f}' if a and b["inp"] else '—'
        print(f'{addr:<44}{sa:>16}{sb:>16}{ch:>12}')

    print()
    print('=== 2. СТОИМОСТЬ ПО РОЛЯМ (пилот 41 док. -> 135 эмитентов) ===')
    for role in ('main', 'esc', 'detect'):
        print(f'\n--- роль {role} ---')
        print(f'{"метка":<22}{"модель":<34}{"вх/вых":>16}{"₽ пилот":>10}{"₽ 135":>9}{"maxout":>8}{"vision":>7}')
        rows = []
        for label, addr in CANDS[role]:
            p = new.get(addr)
            if not p:
                print(f'{label:<22}{addr:<34}{"нет в прайсе":>16}')
                continue
            c = cost(role, p, reasoning_off=(role == 'main' and 'DeepSeek' not in label))
            rows.append((c, label, addr, p))
        for c, label, addr, p in sorted(rows):
            print(f'{label:<22}{addr:<34}{p["inp"]:>7.2f}/{p["out"]:<8.2f}{c:>10.2f}'
                  f'{c * SCALE135:>9.0f}{str(p["maxout"]):>8}{"да" if p["vision"] else "нет":>7}')

    print()
    print('=== 3. СВОДКА: лучший вариант на роль по цене (vision + maxout>=32000) ===')
    for role in ('main', 'esc', 'detect'):
        best = []
        for addr, p in new.items():
            if not p['vision']:
                continue
            try:
                mo = int(p['maxout'])
            except (TypeError, ValueError):
                continue
            if mo < 32000:
                continue
            best.append((cost(role, p, reasoning_off=(role == 'main')), addr, p))
        best.sort()
        print(f'\n  {role}:')
        for c, addr, p in best[:6]:
            print(f'    {addr:<44}{p["inp"]:>7.2f}/{p["out"]:<8.2f} пилот {c:>7.2f} ₽  '
                  f'135 -> {c * SCALE135:>6.0f} ₽  maxout {p["maxout"]}')


if __name__ == '__main__':
    main()