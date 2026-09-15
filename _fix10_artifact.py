# -*- coding: utf-8 -*-
r"""Что записано в артефакте документа: какие страницы считались страницами форм."""
import io, json, os, sys

OUT = r'D:\models\extracted'
for stem in sys.argv[1:] or ['НовосибирскАвтодор_6мес_2025', 'КЛВЗ Кристалл_6мес_2025']:
    p = os.path.join(OUT, stem + '.json')
    if not os.path.exists(p):
        print('%s: артефакта нет' % stem); continue
    r = json.load(io.open(p, encoding='utf-8'))
    print('=' * 70)
    print('%s — статус %s' % (stem, r.get('status')))
    print('  поставщик: %s, модель: %s' % (r.get('source', {}).get('provider'),
                                          r.get('source', {}).get('ocr_model')))
    print('  всего страниц: %s' % r.get('source', {}).get('pages_total'))
    print('  неформные страницы: %s' % json.dumps(
        r.get('source', {}).get('non_form_pages'), ensure_ascii=False))
    for k in ('balance', 'income_statement', 'cash_flow'):
        d = r.get(k)
        if not d:
            print('  %-18s нет' % k); continue
        tp = d.get('transcript_pages') or []
        print('  %-18s строк %3d, страниц транскрипта %s'
              % (k, len(d.get('items') or []), tp))
    print('  проверки: %d, провалено %d'
          % (len(r.get('checks') or []),
             sum(1 for c in (r.get('checks') or []) if not c.get('ok'))))
    print('  предупреждения: %d' % len(r.get('warnings') or []))
    for w in (r.get('warnings') or [])[:5]:
        print('     %s' % w[:130])
