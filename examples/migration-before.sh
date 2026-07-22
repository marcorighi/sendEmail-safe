#!/bin/sh
set -eu

FROM='sender@example.org'
TO='recipient@example.org'
SUBJECT='Legacy sendEmail example'
MESSAGE='This command exposes the SMTP password through -xp.'
SMTP_USER='smtp-login@example.org'
SMTP_PASSWORD='replace-with-a-placeholder-only'

sendEmail \
    -f "$FROM" \
    -t "$TO" \
    -u "$SUBJECT" \
    -m "$MESSAGE" \
    -s smtp-relay.example.org:587 \
    -xu "$SMTP_USER" \
    -xp "$SMTP_PASSWORD" \
    -o tls=yes
