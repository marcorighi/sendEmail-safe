#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate project scripts against Python 3.5 grammar."""
from __future__ import print_function

import ast
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = (
    'sendEmail-safe.py',
    'sendEmail-safe-configure.py',
    'sendEmail-safe-migrate.py'
)


def main():
    failed = False
    for name in SCRIPTS:
        path = os.path.join(ROOT, name)
        with open(path, 'r') as handle:
            source = handle.read()
        try:
            try:
                ast.parse(source, filename=path, feature_version=(3, 5))
            except TypeError:
                # Python 3.5 itself does not expose feature_version. Parsing
                # with the running 3.5 interpreter is already the desired test.
                ast.parse(source, filename=path)
        except SyntaxError as exc:
            print('FAIL {}: {}'.format(name, exc), file=sys.stderr)
            failed = True
        else:
            print('Python 3.5 grammar: OK - ' + name)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
