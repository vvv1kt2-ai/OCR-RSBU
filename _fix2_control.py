# -*- coding: utf-8 -*-
r"""Контрольный опыт: виновата новая подсказка или детекция просто нестабильна?

Новая подсказка у НовосибирскАвтодор_6мес_2025 пометила балансом страницы 1-48 из 49 и
потеряла две формы. Но старые метки того же документа тоже странные (страницы 9-36 без
метки, баланс на стр. 49). Значит возможны две разные причины:

  а) новая подсказка хуже — тогда старая подсказка воспроизведёт старые метки;
  б) детекция нестабильна сама по себе — тогда старая подсказка даст ТРЕТИЙ результат.

Прогоняю СТАРУЮ подсказку заново (платно, ~0.03 ₽ за вызов) на нескольких документах
и сравниваю три набора меток: старый из кэша, новый (v2) и контрольный.
"""
import io, os, re, sys, json

sys.path.insert(0, r'D:\models')
import pipeline as P

PAGES = P.PAGESDIR
SRC = r'D:\data-scraping\downloads'

OLD_PROMPT = ('Даны страницы PDF по порядку (последняя строка каждого приложения = номер страницы). '
              'Определи для каждой формы: balance (Бухгалтерский баланс, 0710001), '
              'income_statement (Отчет о финансовых результатах, 0710002), '
              'cash_flow (Отчет о движении денежных средств, 0710005), other. '
              'Продолжение формы (в шапке "Форма 07100XX с. N") = та же форма. '
              'Ответь ОДНОЙ строкой строго в формате {"1":"other","2":"balance",...} без пояснений.')

DOCS = ['НовосибирскАвтодор_6мес_2025', 'КЛВЗ Кристалл_6мес_2025',
        'Артген (ИСКЧ)_6мес_2025', 'Омега_6мес_2026', 'ИПС_6мес_2025']


def find_pdf(stem):
    for root, _, files in os.walk(SRC):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


def labels(path):
    if not os.path.exists(path):
        return None
    pm = json.load(io.open(path, encoding='utf-8'))
    return {p['page']: p.get('form') for p in pm
            if isinstance(p, dict) and isinstance(p.get('page'), int)}


P.DETECT_PROMPT = OLD_PROMPT   # контроль: возвращаю прежний текст
cost0 = P.USAGE['cost_rub']

print('%-34s %-28s %-28s %s' % ('документ', 'старые метки (кэш)', 'новая подсказка v2',
                                'контроль (старая заново)'))
print('-' * 128)
for stem in DOCS:
    path = find_pdf(stem)
    if not path:
        print('%-34s PDF не найден' % stem[:34]); continue
    old = labels(os.path.join(PAGES, f'_llm_{stem}_detect.json')) or {}
    new = labels(os.path.join(PAGES, f'_llm_{stem}_detect_v2.json')) or {}
    doc = P.pymupdf.open(path)
    npages = len(doc)
    warns = []
    try:
        ctl = labels_from = P.cached_llm(f'{stem}_detect_ctl', lambda: P.detect_pages(
            doc, list(range(1, npages + 1)), npages, warns))
    except Exception as e:
        print('%-34s ОШИБКА контроля: %s' % (stem[:34], str(e)[:60])); doc.close(); continue
    doc.close()
    ctl = {p['page']: p.get('form') for p in (ctl or [])
           if isinstance(p, dict) and isinstance(p.get('page'), int)}

    def brief(m):
        return 'bal=%d inc=%d cf=%d' % (
            sum(1 for v in m.values() if v == 'balance'),
            sum(1 for v in m.values() if v == 'income_statement'),
            sum(1 for v in m.values() if v == 'cash_flow'))
    print('%-34s %-28s %-28s %s' % (stem[:34], brief(old), brief(new), brief(ctl)))
    print('%-34s покрытие: %d/%d, v2: %d/%d, контроль: %d/%d'
          % ('', len(old), npages, len(new), npages, len(ctl), npages))

print()
print('цена контроля: %.3f ₽' % (P.USAGE['cost_rub'] - cost0))
print()
print('КАК ЧИТАТЬ: если контроль совпал со старыми метками — виновата новая подсказка;')
print('если контроль дал третий результат — детекция нестабильна сама по себе.')
