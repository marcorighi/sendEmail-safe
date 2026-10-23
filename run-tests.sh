#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

PYTHON=${PYTHON:-python3}

"$PYTHON" -m unittest discover -s tests -v
"$PYTHON" tests/check_python35_syntax.py
"$PYTHON" -m py_compile \
    sendEmail-safe.py \
    sendEmail-safe-configure.py \
    sendEmail-safe-migrate.py \
    sendEmail-safe-google-auth.py \
    sendemail_safe_google.py

sh -n install.sh
sh -n uninstall.sh
sh -n examples/send-example.sh
sh -n examples/migration-before.sh
sh -n examples/migration-after.sh

printf '\nAll tests completed successfully.\n'
