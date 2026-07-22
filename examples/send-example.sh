#!/bin/sh
set -eu

RECIPIENT=${1:-recipient@example.org}

/usr/local/bin/sendEmail-safe.py \
    --config brevo-personal \
    -t "$RECIPIENT" \
    -u 'sendEmail-safe example' \
    -m 'This message was sent without placing the SMTP password in the process command line.'
