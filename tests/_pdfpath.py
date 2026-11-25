# -*- coding: utf-8 -*-
r"""Где лежит PDF документа: в корне загрузок или в archive/<период>/.

Зачем. Загрузчик раскладывает отчёты по периодам, и во время его работы корень пустеет
и наполняется заново. Тесты, которые открывали `downloads\<имя>.pdf` напрямую, падали на
«PDF отсутствует» — не потому, что сломан код, а потому что файл в этот момент лежал в
`archive/6мес_2026/`. Проверка, которая ломается от раскладки каталога, ничего не говорит
о коде, поэтому путь ищется так же, как его нашёл бы человек: сначала корень, потом архив.
"""
import os

ROOT = r'D:\data-scraping\downloads'


def pdf_path(name, root=ROOT):
    """Полный путь к PDF по имени или None, если файла нет ни в корне, ни в архиве."""
    direct = os.path.join(root, name)
    if os.path.exists(direct):
        return direct
    arch = os.path.join(root, 'archive')
    if os.path.isdir(arch):
        for dirpath, _dirnames, filenames in os.walk(arch):
            if name in filenames:
                return os.path.join(dirpath, name)
    return None


def require(name, root=ROOT):
    """Путь или FileNotFoundError с человеческим текстом."""
    p = pdf_path(name, root)
    if p is None:
        raise FileNotFoundError(f'{name} не найден ни в {root}, ни в {root}\\archive')
    return p