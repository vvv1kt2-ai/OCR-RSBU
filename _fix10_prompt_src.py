# -*- coding: utf-8 -*-
r"""Достаю исходный текст DETECT_PROMPT из коммита до правки 2 (точно, через ast)."""
import ast, hashlib, re, subprocess, sys

COMMIT = sys.argv[1] if len(sys.argv) > 1 else '6eaca25'
src = subprocess.run(['git', 'show', f'{COMMIT}:pipeline.py'],
                     cwd=r'D:\models', capture_output=True).stdout.decode('utf-8')
m = re.search(r"^DETECT_PROMPT = \((.*?)\)\n", src, re.S | re.M)
prompt = ast.literal_eval('(' + m.group(1) + ')')
print('длина: %d' % len(prompt))
print('sha1: %s' % hashlib.sha1(prompt.encode('utf-8')).hexdigest()[:12])
print()
print('--- repr ---')
print(repr(prompt))
