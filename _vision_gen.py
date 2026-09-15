# -*- coding: utf-8 -*-
r"""Готовим слепой тест на зрение: картинка с секретным кодом, который НЕ печатается.

Зачем: в чате с DeepSeek (и его итоговом саммари) утверждается, что plusvibeapi.ru подменяет
модели, и что конкретно deepseek-v4.1-flash «слеп» — картинок не видит, хотя по спецификации
у него нативное зрение. Для нас это не абстракция: детекция и транскрипция шлют модели именно
ИЗОБРАЖЕНИЯ страниц (pipeline.py:1168 и 1081), поэтому слепая модель обнулила бы обе роли.

Проверяем не рассуждением, а опытом. Тест должен быть слепым: код кладём в файл и НЕ печатаем,
иначе «успех» ничего не докажет — я мог бы назвать код по памяти. Читателей трое:
  1) я сам (модель агента) — через инструмент чтения картинок;
  2) модель детекции у plusvibe (deepseek-v4.1-flash);
  3) модель транскрипции у plusvibe (gemini-3.8-flash).
Если картинку прочтут все трое — слепоты у этих ролей нет, и подозрение к нашему конвейеру
не относится (значит, оно про другой канал или другую модель).
"""
import io, os, random, sys

sys.path.insert(0, r'D:\models\pylibs')
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

OUT = r'D:\models\_vision_test.png'
SECRET = r'D:\models\_vision_secret.txt'

ALPHABET = 'FGJLQRSUVWZ2456789'   # без кириллических двойников: A/B/C/E/H/K/M/N/O/P/T/X/Y
                                  # модель записывает их кириллицей (H->Н, E->Е), и сравнение
                                  # строк ломается на ровном месте — проверено опытом
code = ''.join(random.choice(ALPHABET) for _ in range(6))
word = 'БУХГАЛТЕРСКИЙ БАЛАНС'

img = Image.new('RGB', (1000, 560), 'white')
d = ImageDraw.Draw(img)
big = ImageFont.truetype(r'C:\Windows\Fonts\arialbd.ttf', 130)
mid = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', 54)
small = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', 30)

d.text((60, 40), word, font=mid, fill='black')
d.text((60, 150), code, font=big, fill='black')
# Рамка и подпись — чтобы картинка была похожа на фрагмент формы, а не на синтетику.
d.rectangle([40, 130, 960, 320], outline='black', width=3)
d.text((60, 380), 'Код строки 1700: 969 421', font=small, fill='black')
d.text((60, 430), 'На 30 июня 2026 г.', font=small, fill='black')

img.save(OUT)
# Контроль: чистый белый лист. Если модель «прочитает» код и здесь — она его выдумывает,
# и тогда тест недействителен в обратную сторону.
Image.new('RGB', (1000, 560), 'white').save(r'D:\models\_vision_blank.png')
with io.open(SECRET, 'w', encoding='utf-8') as fh:
    fh.write(code + '\n')

# Печатаем всё, кроме секрета.
print('картинка: %s (%d x %d, %d байт)' % (OUT, img.size[0], img.size[1], os.path.getsize(OUT)))
print('секрет записан в отдельный файл — в выводе его нет намеренно')
print('проверка: секрет в выводе не встречается —', code not in '')
print('длина секрета: %d знаков' % len(code))
