# -*- coding: utf-8 -*-
r"""Диагностика: ЧТО именно читают роли с картинки. Секрет здесь печатается — это уже не
слепой тест, а разбор ошибки, и код генерируется заново на каждый опыт.

Слепой опыт (_vision_pv.py) показал: main (gemini) читает код верно, а detect (deepseek) и
esc (anthropic) дают ответ длиной 6 знаков, но НЕ тот код, при этом на белом листе оба честно
отвечают «НЕ ВИЖУ». Полная слепота так себя не ведёт: слепая модель не отличала бы пустой лист
от заполненного. Значит дело в искажении чтения. Возможные причины — и что их различит:

  A. Модель видит изображение, но мелкий шрифт ей недоступен; крупный код читает.
     Проверка: код нарисовать ОЧЕНЬ крупно и отдельно — если прочтёт, дело в размере.
  B. Модель читает не тот фрагмент (например, берёт «969421» вместо кода).
     Проверка: печатаем ответ и секрет рядом — видно, что именно она назвала.
  C. Модель выдумывает правдоподобную строку: ответ нестабилен между повторами.
     Проверка: три повтора одного вопроса на одной картинке — сравниваем ответы между собой.
  D. Модель искажает отдельные знаки (Z как 2, 8 как B) — ответ near-miss.
     Проверка: посимвольное сравнение с секретом.

Печатаем: секрет, ответ, число совпавших знаков и стабильность повторов.
"""
import base64, io, random, sys

sys.path.insert(0, r'D:\models')
sys.path.insert(0, r'D:\models\pylibs')
import pipeline as P  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ALPHABET = '2456789ACEFHKMNPRTUXZ'
WORD = 'БУХГАЛТЕРСКИЙ БАЛАНС'
Q = ('Какой код написан крупными знаками в рамке на этом изображении? '
     'Ответь только самим кодом, без пояснений. Если текста не видно, ответь: НЕ ВИЖУ.')


def make(path, code, scale=1.0, extra=True):
    img = Image.new('RGB', (1200, 620), 'white')
    d = ImageDraw.Draw(img)
    mid = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', int(54 * scale))
    big = ImageFont.truetype(r'C:\Windows\Fonts\arialbd.ttf', int(150 * scale))
    small = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', int(30 * scale))
    d.text((60, 30), WORD, font=mid, fill='black')
    d.rectangle([40, 130, 1150, 330], outline='black', width=3)
    d.text((60, 140), code, font=big, fill='black')
    if extra:
        d.text((60, 400), 'Код строки 1700: 969 421', font=small, fill='black')
        d.text((60, 450), 'На 30 июня 2026 г.', font=small, fill='black')
    img.save(path)
    return path


def ask(model, path):
    b64 = base64.b64encode(io.open(path, 'rb').read()).decode('ascii')
    try:
        txt, _ = P.chat([P.img_message(b64, Q)], model, temperature=0, max_tokens=2000)
        return ' '.join((txt or '').split())
    except Exception as e:
        return 'ОШИБКА: %s' % str(e)[:90]


def clean(s):
    import re
    return re.sub(r'[^0-9A-Za-zА-Яа-я]', '', s or '').upper()


c0, n0 = P.USAGE.get('cost_rub', 0.0), P.USAGE.get('calls', 0)
roles = [('detect: deepseek', P.M_DETECT), ('main: gemini', P.M_MAIN), ('esc: anthropic', P.M_ESC)]

print('=== опыт 1: обычная картинка, три роли, ответ печатаем открыто')
code = ''.join(random.choice(ALPHABET) for _ in range(6))
p = make(r'D:\models\_vd1.png', code)
print('   СЕКРЕТ: %s' % code)
for label, m in roles:
    a = ask(m, p)
    c = clean(a)
    same = sum(1 for x, y in zip(c, code) if x == y)
    print('   %-17s ответ: %-24s совпало знаков: %d из %d' % (label, a[:24], same, len(code)))
    # если ответ не совпал, но содержит «969421» или иное число — покажем отдельно
    if '969421' in c.replace(' ', ''):
        print('        ^ похоже, модель назвала контрольное число 969421, а не код')
print()

print('=== опыт 2: стабильность — три повтора на одной картинке (детекция)')
for i in range(3):
    a = ask(P.M_DETECT, p)
    print('   повтор %d: %s' % (i + 1, a[:50]))
print()

print('=== опыт 3: код нарисован очень крупно (только код, без прочего текста)')
code2 = ''.join(random.choice(ALPHABET) for _ in range(4))
img = Image.new('RGB', (1200, 500), 'white')
d = ImageDraw.Draw(img)
d.text((40, 160), code2, font=ImageFont.truetype(r'C:\Windows\Fonts\arialbd.ttf', 240), fill='black')
p2 = r'D:\models\_vd3.png'
img.save(p2)
print('   СЕКРЕТ: %s' % code2)
for label, m in roles:
    a = ask(m, p2)
    print('   %-17s ответ: %s' % (label, a[:40]))
print()

print('=== опыт 4: простая просьба — прочитать слово на картинке')
Q2 = 'Прочитай, что написано на изображении. Ответь одной строкой.'
p3 = make(r'D:\models\_vd4.png', code2)
for label, m in roles:
    b64 = base64.b64encode(io.open(p3, 'rb').read()).decode('ascii')
    try:
        txt, _ = P.chat([P.img_message(b64, Q2)], m, temperature=0, max_tokens=2000)
        print('   %-17s %s' % (label, ' '.join((txt or '').split())[:70]))
    except Exception as e:
        print('   %-17s ОШИБКА %s' % (label, str(e)[:70]))

print()
print('вызовов: %d, цена: %.4f ₽' % (P.USAGE.get('calls', 0) - n0, P.USAGE.get('cost_rub', 0.0) - c0))
