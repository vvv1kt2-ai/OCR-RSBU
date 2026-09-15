# -*- coding: utf-8 -*-
r"""Почему поставщик отбивает вызовы с HTTP 400 «Некорректный запрос».

Факты из лога поставщика (plusvibe-usage.ndjson), а не из рассуждения:
  * отказы НЕ списываются (за все 16 754 вызова за не-200 статусы списано 0.01 ₽) — деньги не теряем;
  * но их много: у эскалации 24 из 75 вызовов (32%), у основной модели 15%, у детекции ~3%;
  * приходят они БЫСТРО (p50 около 0.5 с), значит сервер отказывает до обработки содержимого;
  * два документа пилота упали целиком именно на них.
Отсюда рабочая гипотеза: отказ по РАЗМЕРУ запроса. Эскалация читает страницу на 300 dpi
(в 2.25 раза больше пикселей, чем 200 dpi), то есть её запросы самые тяжёлые — и доля отказов
у неё самая высокая. Если это так, лечится уменьшением разрешения/качества, а не сменой
поставщика.

Здесь: (1) измеряем размер тела запроса для 200 и 300 dpi — бесплатно, без сети;
       (2) пробуем настоящие вызовы на 200 и 300 dpi и смотрим, где приходит 400.
"""
import base64, io, json, os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

DOC = 'НовосибирскАвтодор_6мес_2026'
PROMPT = 'Перепиши таблицу этой страницы в markdown, сохрани все числа.'


def find_pdf(stem):
    for root, _, files in os.walk(P.DOWNLOADS):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


path = find_pdf(DOC)
doc = P.pymupdf.open(path)
print('документ: %s, страниц %d' % (DOC, len(doc)))
print()
print('=== 1. размер тела запроса (моментальный снимок, без сети)')
print('  %-6s %10s %10s %14s %14s' % ('стр.', 'px', 'PNG КБ', 'base64 КБ', 'тело МБ'))
sizes = {}
for p in (2, 3):
    for dpi in (200, 300):
        b64 = P.render_png(doc[p - 1], dpi)
        png = len(base64.b64decode(b64))
        body = len(json.dumps({'model': 'x', 'messages': [
            {'role': 'user', 'content': [{'type': 'image_url',
                                          'image_url': {'url': 'data:image/png;base64,' + b64}}]}]}).encode())
        pg = doc[p - 1]
        sz = pg.get_pixmap(dpi=dpi)
        sizes[(p, dpi)] = body
        print('  %-6d %10s %10.0f %14.0f %14.2f'
              % (p, '%dx%d' % (sz.width, sz.height), png / 1024, len(b64) / 1024, body / 1048576))
print()
print('=== 2. живые вызовы: где приходит 400')
print('  %-8s %-14s %-8s %s' % ('стр.', 'модель', 'dpi', 'результат'))
c0, n0 = P.USAGE.get('cost_rub', 0.0), P.USAGE.get('calls', 0)
for dpi, model, label in ((200, P.M_MAIN, 'main'), (300, P.M_ESC, 'esc')):
    for p in (2, 3):
        b64 = P.render_png(doc[p - 1], dpi)
        try:
            txt, fin = P.chat([P.img_message(b64, PROMPT)], model, temperature=0, max_tokens=3000)
            res = 'ок, знаков %d' % len(txt)
        except Exception as e:
            res = str(e)[:110]
        print('  %-8d %-14s %-8d %s' % (p, label, dpi, res), flush=True)
doc.close()
print()
print('вызовов: %d, цена: %.4f ₽' % (P.USAGE.get('calls', 0) - n0, P.USAGE.get('cost_rub', 0.0) - c0))
