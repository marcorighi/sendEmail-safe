#!/bin/sh
set -eu

FROM='sender@example.org'
TO='recipient@example.org'
SUBJECT='Migrated sendEmail-safe example'
MESSAGE='The SMTP password is read from the selected profile.'

/usr/local/bin/sendEmail-safe.py \
    --config brevo-server \
    -f "$FROM" \
    -t "$TO" \
    -u "$SUBJECT" \
    -m "$MESSAGE"
