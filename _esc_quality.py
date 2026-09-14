# -*- coding: utf-8 -*-
r"""Качество эскалации: модель эскалации Polza против модели эскалации PlusVibe.

Судит текстовый слой PDF — единственная бесплатная истина. Проверка идёт через тот же
производственный шов, что и конвейер: `pipeline.transcribe_cached(doc, p, dpi=300,
model=M_ESC)`. Транскрипты Polza уже лежат в кэше и бесплатны; для PlusVibe они
создаются заново (7 страниц ≈ 5 ₽) и кэшируются под своим именем.

Запуск:  $env:PILOT_PROVIDER='plusvibe'; python _esc_quality.py
"""
import io, os, re, json, sys, hashlib

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR
import _pv_quality as Q
import fitz

EX = r'D:\models\extracted'
DL = r'D:\data-scraping\downloads'
TARGETS = r'D:\models\_esc_targets.json'


def main():
    pv = PR.active('plusvibe')
    pz = PR.active('polza')
    targets = json.load(io.open(TARGETS, encoding='utf-8'))
    print('страниц к проверке: %d' % len(targets))
    print('профиль: %s, модель эскалации len=%d' % (pv.name, len(P.M_ESC)))
    print()

    rows = []
    print('%-30s %4s %9s %9s %9s %9s %9s'
          % ('документ', 'стр', 'слой', 'Polza', 'подтв', 'PlusVibe', 'подтв'))
    print('%-30s %4s %9s %9s %9s %9s %9s'
          % ('', '', 'чисел', 'чисел', 'слоем', 'чисел', 'слоем'))
    print('-' * 84)

    for t in targets:
        stem, page = t['stem'], t['page']
        pdf = os.path.join(DL, stem + '.pdf')
        d = fitz.open(pdf)
        try:
            layer = d[page - 1].get_text()
            lnum = set(Q.norm_digits(layer))
            # транскрипт Polza — из кэша, бесплатно
            pz_path = P.page_cache_path(d, stem + '.pdf', page, 300, P.M_ESC, profile=pz)
            pz_txt = (io.open(pz_path, encoding='utf-8').read()
                      if os.path.exists(pz_path) else '')
            # транскрипт PlusVibe — производственный вызов, кэшируется
            pv_txt = P.transcribe_cached(d, page, name=stem + '.pdf', dpi=300,
                                         model=P.M_ESC)
        finally:
            d.close()

        def nums(txt):
            return [x for x in Q.norm_digits(txt) if len(x) >= 4]

        def confirmed(txt):
            n = nums(txt)
            ok = [x for x in n if x in lnum]
            bad = [x for x in n if x not in lnum]
            return len(n), len(ok), bad

        def missed(txt):
            """числа текстового слоя, которых нет в транскрипте: потеря"""
            have = set(nums(txt))
            return [x for x in sorted(lnum) if len(x) >= 4 and x not in have]

        pz_n, pz_ok, pz_bad = confirmed(pz_txt)
        pv_n, pv_ok, pv_bad = confirmed(pv_txt)
        pz_miss, pv_miss = missed(pz_txt), missed(pv_txt)
        print('%-30s %4d %9d %9d %9d %9d %9d'
              % (stem[:30], page, len(lnum), pz_n, pz_ok, pv_n, pv_ok))
        if pz_bad:
            print('      Polza выдумала: %s' % ', '.join(pz_bad[:6]))
        if pv_bad:
            print('      PlusVibe выдумала: %s' % ', '.join(pv_bad[:6]))
        rows.append({'stem': stem, 'page': page, 'layer_numbers': len(lnum),
                     'pz_numbers': pz_n, 'pz_ok': pz_ok, 'pz_bad': pz_bad,
                     'pv_numbers': pv_n, 'pv_ok': pv_ok, 'pv_bad': pv_bad,
                     'pz_missed': pz_miss, 'pv_missed': pv_miss,
                     'pz_len': len(pz_txt), 'pv_len': len(pv_txt),
                     'same': pz_txt.strip() == pv_txt.strip()})

    print('-' * 84)
    print('%-30s %4s %9s %9d %9d %9d %9d'
          % ('ИТОГО', '', '', sum(r['pz_numbers'] for r in rows),
             sum(r['pz_ok'] for r in rows), sum(r['pv_numbers'] for r in rows),
             sum(r['pv_ok'] for r in rows)))
    print()
    print('=== выдуманные числа (4+ знака, которых нет в текстовом слое) ===')
    print('Polza:    %d' % sum(len(r['pz_bad']) for r in rows))
    print('PlusVibe: %d' % sum(len(r['pv_bad']) for r in rows))
    print()
    print('=== полнота: числа текстового слоя, которых нет в транскрипте ===')
    print('%-32s %4s %8s %10s' % ('документ', 'стр', 'Polza', 'PlusVibe'))
    for r in rows:
        print('  %-30s %4d %8d %10d'
              % (r['stem'][:30], r['page'], len(r['pz_missed']),
                 len(r['pv_missed'])))
    print('  %-30s %4s %8d %10d'
          % ('ИТОГО', '', sum(len(r['pz_missed']) for r in rows),
             sum(len(r['pv_missed']) for r in rows)))
    print()
    print('транскрипты совпали посимвольно: %d из %d'
          % (sum(1 for r in rows if r['same']), len(rows)))

    json.dump(rows, io.open(r'D:\models\_esc_quality.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('токены: pt=%d ct=%d, стоимость %.4f ₽'
          % (P.USAGE['prompt'], P.USAGE['completion'], P.USAGE['cost_rub']))
    print('-> _esc_quality.json')


if __name__ == '__main__':
    main()
