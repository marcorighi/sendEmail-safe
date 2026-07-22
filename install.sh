#!/bin/sh
set -eu

PREFIX=${PREFIX:-/usr/local}
BINDIR=${BINDIR:-$PREFIX/bin}

if [ "$(id -u)" -ne 0 ]; then
    echo "install.sh must be run as root." >&2
    exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

install -d -o root -g root -m 0755 "$BINDIR"
install -o root -g root -m 0755 \
    "$SCRIPT_DIR/sendEmail-safe.py" \
    "$SCRIPT_DIR/sendEmail-safe-configure.py" \
    "$SCRIPT_DIR/sendEmail-safe-migrate.py" \
    "$BINDIR/"

printf 'Installed:\n'
printf '  %s/sendEmail-safe.py\n' "$BINDIR"
printf '  %s/sendEmail-safe-configure.py\n' "$BINDIR"
printf '  %s/sendEmail-safe-migrate.py\n' "$BINDIR"
printf '\nUser profiles were not created or modified.\n'
