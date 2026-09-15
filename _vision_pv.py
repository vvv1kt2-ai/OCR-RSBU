# -*- coding: utf-8 -*-
r"""Слепой тест зрения у ролей plusvibe. Секрет НЕ печатается, сравнение идёт в коде.

Повод: в итоговом саммари чата утверждается, что plusvibeapi.ru подменяет модели и что
конкретно deepseek-v4.1-flash «слеп» — картинок не видит. Для нас это не абстракция: и
разметка страниц, и расшифровка таблиц шлют модели ИЗОБРАЖЕНИЯ (pipeline.py:1168, 1081),
поэтому слепая модель обнулила бы обе роли. Косвенный довод в пользу проверки: сама эта
среда только что отказалась читать картинку с формулировкой «модель deepseek-v4.1-flash
не заявляет поддержку изображений».

Устройство теста. На картинке нарисован случайный код из 6 знаков; код лежит в отдельном
файле и в вывод не попадает. Спрашиваем три роли так же, как это делает конвейер, и СРАВНИВАЕМ
ответ с секретом внутри скрипта. Снаружи печатается только вердикт, поэтому «успех» нельзя
подделать знанием кода. Контроль — чистый белый лист: если модель «читает» код и там, значит
она его выдумывает, и тест недействителен в обратную сторону.

Роль esc (anthropic) проверяем тоже: если она слепа, эскалация бессмысленна, а это 59% цены.
"""
import base64, io, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

IMG = r'D:\models\_vision_test.png'
BLANK = r'D:\models\_vision_blank.png'
SECRET = r'D:\models\_vision_secret.txt'
Q = ('Какой код написан крупными знаками в рамке на этом изображении? '
     'Ответь только самим кодом, без пояснений. Если текста не видно, ответь: НЕ ВИЖУ.')

secret = io.open(SECRET, encoding='utf-8').read().strip()


# Кириллические двойники латинских букв: модель читает верно, но записывает букву
# кириллицей (H -> Н, E -> Е), и строгое сравнение строк объявляет это ошибкой чтения.
# Опыт 16.09.2026 показал ровно это: ответ «Н9ЕЕНК» вместо «H9EENK» — прочитано верно.
HOMOGLYPHS = {'А': 'A', 'В': 'B', 'С': 'C', 'Е': 'E', 'Н': 'H', 'К': 'K', 'М': 'M',
              'О': 'O', 'Р': 'P', 'Т': 'T', 'Х': 'X', 'У': 'Y', 'З': '3', 'В': 'B'}


def verdict(answer):
    """Сравнение с секретом — здесь и только здесь. Наружу уходит вердикт, не ответ."""
    import re
    raw = (answer or '').upper()
    a = re.sub(r'[^0-9A-ZА-Я]', '', raw)
    # сначала строго, затем с заменой кириллических двойников на латиницу
    variants = [a, ''.join(HOMOGLYPHS.get(ch, ch) for ch in a)]
    s = re.sub(r'[^0-9A-Z]', '', secret).upper()
    if s and any(s == v for v in variants):
        if variants[0] != variants[1]:
            return 'СОВПАЛО (буквы записаны кириллическими двойниками — чтение верное)'
        return 'СОВПАЛО — картинку прочитал верно'
    if 'НЕВИЖУ' in re.sub(r'\s', '', raw):
        return 'НЕ ВИЖУ — модель заявила, что изображения нет'
    if not a:
        return 'ПУСТОЙ ОТВЕТ'
    return 'другое (длина ответа %d, наш код %d)' % (len(a), len(s))


def ask(label, model, path):
    b64 = base64.b64encode(io.open(path, 'rb').read()).decode('ascii')
    try:
        txt, fin = P.chat([P.img_message(b64, Q)], model, temperature=0, max_tokens=2000)
    except Exception as e:
        print('  %-22s ОШИБКА: %s' % (label, str(e)[:110]))
        return
    print('  %-22s %s   (finish=%s)' % (label, verdict(txt), fin))


c0, n0 = P.USAGE.get('cost_rub', 0.0), P.USAGE.get('calls', 0)
print('секрет: 6 знаков, в вывод не печатается')
print()
print('=== читает ли картинку с кодом')
ask('detect (deepseek)', P.M_DETECT, IMG)
ask('main (gemini)', P.M_MAIN, IMG)
ask('esc (anthropic)', P.M_ESC, IMG)
print()
print('=== контроль: белый лист, текста нет')
ask('detect (deepseek)', P.M_DETECT, BLANK)
ask('main (gemini)', P.M_MAIN, BLANK)
print()
print('вызовов: %d, цена: %.4f ₽' % (P.USAGE.get('calls', 0) - n0, P.USAGE.get('cost_rub', 0.0) - c0))
