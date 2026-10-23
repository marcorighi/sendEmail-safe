#!/bin/sh
set -eu

PREFIX=${PREFIX:-/usr/local}
BINDIR=${BINDIR:-$PREFIX/bin}

if [ "$(id -u)" -ne 0 ]; then
    echo "uninstall.sh must be run as root." >&2
    exit 1
fi

rm -f \
    "$BINDIR/sendEmail-safe.py" \
    "$BINDIR/sendEmail-safe-configure.py" \
    "$BINDIR/sendEmail-safe-migrate.py" \
    "$BINDIR/sendEmail-safe-google-auth.py" \
    "$BINDIR/sendemail_safe_google.py"

printf 'Removed sendEmail-safe programs from %s.\n' "$BINDIR"
printf 'User profiles were deliberately left unchanged.\n'
