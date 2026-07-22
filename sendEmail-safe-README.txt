SENDEMAIL-SAFE OPERATIONAL GUIDE
===============================

Purpose
-------

sendEmail-safe.py sends email without placing the SMTP password in the
process argument list. It reads the complete SMTP configuration from a private
JSON profile belonging to the effective user.

Compatibility
-------------

Python 3.5.3 and later. Only the Python standard library is required.

Installation
------------

Run:

  sudo ./install.sh

The installed commands are:

  /usr/local/bin/sendEmail-safe.py
  /usr/local/bin/sendEmail-safe-configure.py
  /usr/local/bin/sendEmail-safe-migrate.py

Creating profiles
-----------------

Run the configurator as the user who will send the email:

  sendEmail-safe-configure.py --config brevo-personal
  sendEmail-safe-configure.py --config brevo-work

For scripts executed by root:

  sudo sendEmail-safe-configure.py --config brevo-server

A simple profile name resolves to:

  ~/.config/sendemail-safe/PROFILE.json

Examples:

  /home/alice/.config/sendemail-safe/brevo-personal.json
  /home/alice/.config/sendemail-safe/brevo-work.json
  /root/.config/sendemail-safe/brevo-server.json

The profile directory is mode 0700. Each profile is mode 0600. The SMTP
password and the complete SMTP configuration are stored in clear text.

Sending a message
-----------------

  sendEmail-safe.py \
    --config brevo-personal \
    -t recipient@example.org \
    -u 'Test message' \
    -m 'This is a test.'

The -xp option is forbidden. The password is always read from the selected
profile.

A message body supplied with -m remains visible in the process argument list.
For sensitive text, use a private file:

  sendEmail-safe.py \
    --config brevo-personal \
    -t recipient@example.org \
    -u 'Private message' \
    -o message-file="$HOME/private-message.txt"

Migration
---------

  python3 sendEmail-safe-migrate.py \
    --config brevo-server \
    adminscript userscript

The migration utility creates a backup, replaces sendEmail, adds the selected
profile, removes -xp, and normally removes -s, -xu, and -o tls=... so that the
profile contains the full SMTP configuration. It then runs bash -n on every
modified shell script.

To keep SMTP overrides while removing the password argument:

  python3 sendEmail-safe-migrate.py \
    --config brevo-server \
    --keep-smtp-overrides \
    adminscript

Backups are stored in:

  ~/.local/state/sendemail-safe-backups/

Always inspect the diff before deployment or commit.

Verification
------------

Search for residual -xp options:

  grep -RIn --exclude-dir=.git --exclude-dir=.svn -- '-xp' .

Observe the process during delivery:

  watch -n 0.1 \
    'ps -eo pid,user,comm,args --width 500 | grep -E "[s]endEmail-safe"'

The profile name may be visible, but the SMTP password must not appear.

Security boundary
-----------------

This design removes the password from /proc/PID/cmdline and ordinary process
listings. It does not protect the clear-text profile from its owner or root and
cannot prevent a privileged actor from inspecting process memory while the
password is being used.

Testing
-------

  ./run-tests.sh

Uninstallation
--------------

  sudo ./uninstall.sh

Profiles are not deleted by the uninstaller.

Documentation
-------------

See README.md, SECURITY.md, and the files in examples/ for complete details.
