# sendEmail-safe

`sendEmail-safe.py` is a small Linux command-line mail sender designed for shell scripts that currently use the legacy `sendEmail` program with `-xp PASSWORD`.

The original `sendEmail` invocation places the SMTP password in the process argument list. While the process is running, the credential may be visible through tools and interfaces such as `ps`, `pgrep -a`, and `/proc/<pid>/cmdline`.

`sendEmail-safe.py` removes that exposure by reading the password from a private, per-user JSON profile. The profile may contain the complete SMTP configuration in clear text and must be owned by the user with mode `0600`.

## Main properties

- The SMTP password is not passed as a command-line argument.
- Each operating-system user has independent profiles in their own home directory.
- Each user may create multiple profiles and select one with `--config`.
- A simple profile name resolves to `~/.config/sendemail-safe/PROFILE.json`.
- Explicit profile paths are accepted only inside the effective user's home directory.
- Profile ownership and permissions are checked before use.
- Core dumps are disabled and the process is marked non-dumpable on Linux where supported.
- Common `sendEmail` options are supported to simplify migration.
- A migration utility updates shell scripts and creates a backup before writing.
- The implementation uses only the Python standard library.
- The three programs are written for Python 3.5.3 and later.

## Threat model and limitations

This project addresses one specific problem: exposing an SMTP password in the process command line.

It does **not** protect the password from:

- the owner of the profile file;
- `root`, the kernel, or a sufficiently privileged debugger;
- an attacker who compromises the account running the program;
- unprotected backups containing the profile;
- disk access that bypasses normal file permissions;
- memory inspection by a privileged actor while SMTP authentication is occurring.

The password is stored in clear text by design. It is briefly present in the Python process memory during authentication.

Other command-line values may remain visible, including recipients, subject text, attachment paths, and a body supplied with `-m`. To avoid exposing a sensitive message body in the process list, place it in a file and use:

```bash
-o message-file=/path/to/private-message.txt
```

## Repository files

- `sendEmail-safe.py` — SMTP sender.
- `sendEmail-safe-configure.py` — interactive profile creator and editor.
- `sendEmail-safe-migrate.py` — shell-script migration utility.
- `sendEmail-safe-README.txt` — plain-text operational guide.
- `install.sh` and `uninstall.sh` — system-wide installation helpers.
- `examples/` — example profile and invocation.
- `tests/` — unit tests and Python 3.5 grammar check.

## Installation

Run:

```bash
sudo ./install.sh
```

The programs are installed as:

```text
/usr/local/bin/sendEmail-safe.py
/usr/local/bin/sendEmail-safe-configure.py
/usr/local/bin/sendEmail-safe-migrate.py
```

Manual installation is also possible:

```bash
sudo install -o root -g root -m 0755 \
  sendEmail-safe.py \
  sendEmail-safe-configure.py \
  sendEmail-safe-migrate.py \
  /usr/local/bin/
```

No external Python packages are required.

## Creating profiles

Run the configurator as the user who will send the email. Do not use `sudo` when creating a normal user's profile.

```bash
sendEmail-safe-configure.py --config brevo-personal
sendEmail-safe-configure.py --config brevo-work
```

For a root cron job:

```bash
sudo sendEmail-safe-configure.py --config brevo-server
```

The resulting files are stored separately:

```text
/home/alice/.config/sendemail-safe/brevo-personal.json
/home/alice/.config/sendemail-safe/brevo-work.json
/root/.config/sendemail-safe/brevo-server.json
```

The profile directory is set to mode `0700`, and each profile is set to mode `0600`.

A simple name is resolved automatically:

```text
--config brevo-work
    -> ~/.config/sendemail-safe/brevo-work.json
```

An explicit path is also accepted if it remains inside the effective user's home:

```bash
sendEmail-safe.py \
  --config ~/.config/sendemail-safe/brevo-work.json \
  ...
```

## Profile format

A complete authenticated STARTTLS profile looks like this:

```json
{
  "auth": true,
  "from": "sender@example.org",
  "host": "smtp-relay.example.org",
  "password": "replace-with-the-real-smtp-password",
  "port": 587,
  "security": "starttls",
  "timeout": 30.0,
  "tls_verify": true,
  "user": "smtp-login@example.org"
}
```

Optional fields are:

```json
{
  "ca_file": "~/certificates/custom-ca.pem",
  "log": "~/logs/sendemail-safe.log",
  "reply_to": "replies@example.org"
}
```

Supported security modes:

- `starttls` — require STARTTLS before authentication.
- `ssl` — use implicit TLS, commonly on port 465.
- `auto` — use STARTTLS when advertised, otherwise continue without it.
- `plain` — use an unencrypted SMTP connection.

`plain` and the fallback behavior of `auto` should be used only on trusted networks or with a local relay.

Unauthenticated SMTP can be configured with:

```json
{
  "auth": false,
  "from": "sender@example.org",
  "host": "localhost",
  "password": "",
  "port": 25,
  "security": "plain",
  "timeout": 30.0,
  "tls_verify": true,
  "user": ""
}
```

## Sending an email

```bash
sendEmail-safe.py \
  --config brevo-personal \
  -t recipient@example.org \
  -u 'Test message' \
  -m 'This is a test.'
```

The sender, SMTP host, port, login, password, security mode, timeout, and TLS verification settings are read from the selected profile.

Multiple recipients and attachments are supported:

```bash
sendEmail-safe.py \
  --config brevo-work \
  -t first@example.org second@example.org \
  -cc manager@example.org \
  -u 'Report' \
  -m 'The report is attached.' \
  -a report.pdf data.csv
```

HTML body:

```bash
sendEmail-safe.py \
  --config brevo-work \
  -t recipient@example.org \
  -u 'HTML message' \
  -m '<p>Hello</p>' \
  -o message-content-type=text/html
```

Body from a private file:

```bash
sendEmail-safe.py \
  --config brevo-work \
  -t recipient@example.org \
  -u 'Private message' \
  -o message-file="$HOME/private-message.txt"
```

## Supported command-line options

The supported compatibility subset is:

```text
-C, --config PROFILE_OR_PATH
-f FROM
-t TO...
-cc TO...
-bcc TO...
-u SUBJECT
-m TEXT
-a FILE...
-l LOG_FILE
-q
-v
-s HOST:PORT
-xu USER
-o fqdn=NAME
-o message-charset=CHARSET
-o message-content-type=text/plain|text/html
-o message-file=FILE
-o reply-to=ADDRESS
-o timeout=SECONDS
-o tls=yes|no
```

`-xp` is always rejected. Unknown options are rejected rather than silently ignored.

This is a compatibility-oriented subset, not a claim of complete behavioral equivalence with every `sendEmail` release and option.

## Migrating shell scripts

First create the selected profile for the user who will execute the scripts. Then run the migration utility from the root of the script tree:

```bash
python3 sendEmail-safe-migrate.py \
  --config brevo-server \
  adminscript \
  userscript
```

The utility initially performs a dry inspection and displays the files and operations it intends to apply. After confirmation, it:

1. creates a private compressed backup;
2. replaces `sendEmail` with the `sendEmail-safe.py` executable located alongside the migration utility (typically `/usr/local/bin/sendEmail-safe.py` for a manual installation or `/usr/bin/sendEmail-safe.py` for distribution packages);
3. adds `--config PROFILE`;
4. removes `-xp` and its value;
5. removes `-s`, `-xu`, and `-o tls=...` by default so that the selected profile is the SMTP source of truth;
6. preserves file ownership and permissions by rewriting the existing inode;
7. validates every modified shell script with `bash -n`.

Example transformation:

```bash
sendEmail \
  -f "$FROM" \
  -t "$TO" \
  -u "$SUBJECT" \
  -m "$MESSAGE" \
  -s smtp-relay.example.org:587 \
  -xu "$SMTP_USER" \
  -xp "$SMTP_PASSWORD" \
  -o tls=yes
```

becomes:

```bash
/usr/local/bin/sendEmail-safe.py \
  --config brevo-server \
  -f "$FROM" \
  -t "$TO" \
  -u "$SUBJECT" \
  -m "$MESSAGE"
```

To retain the existing host, user, and TLS overrides while still removing `-xp`:

```bash
python3 sendEmail-safe-migrate.py \
  --config brevo-server \
  --keep-smtp-overrides \
  adminscript
```

To suppress the confirmation prompt after reviewing the command and testing on a copy:

```bash
python3 sendEmail-safe-migrate.py \
  --config brevo-server \
  --yes \
  adminscript
```

Backups are written to:

```text
~/.local/state/sendemail-safe-backups/
```

The migration utility uses a conservative shell lexer rather than a full shell parser. Always inspect the resulting diff before committing or deploying the scripts.

## Verification

Search for residual password arguments:

```bash
grep -RIn \
  --exclude-dir=.git \
  --exclude-dir=.svn \
  -- '-xp' \
  adminscript userscript
```

Observe the new process during a real delivery:

```bash
watch -n 0.1 \
  'ps -eo pid,user,comm,args --width 500 | grep -E "[s]endEmail-safe"'
```

The selected profile name and non-secret message arguments may be visible. The SMTP password must not appear.

## Testing

Run:

```bash
./run-tests.sh
```

or:

```bash
make test
```

The test suite checks migration behavior, profile resolution, password-option rejection, message construction, shell syntax, and Python 3.5 grammar compatibility.

The source avoids syntax introduced after Python 3.5. Runtime testing should still be performed on the oldest Python interpreter used in production because the current automated environment may not provide an actual Python 3.5.3 binary.

## Uninstallation

```bash
sudo ./uninstall.sh
```

The uninstaller removes the three installed programs. It deliberately does not remove any user's profiles.

## Security reporting

See [SECURITY.md](SECURITY.md). Never include a real SMTP password, profile file, process dump, or unredacted script in a public issue.

## Authorship and AI assistance

Marco Righi conceived the project requirements, identified the operational problem, directed the implementation, and performed the deployment-oriented review and testing.

The initial implementation, migration logic, tests, and documentation were generated with assistance from ChatGPT by OpenAI through an interactive design process. The human maintainer retains responsibility for reviewing, testing, publishing, and maintaining the project.

See [AUTHORS.md](AUTHORS.md) and [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).

## License

This project is released under the MIT License. See [LICENSE](LICENSE).

## Non-affiliation notice

This project is not affiliated with, sponsored by, or endorsed by the original `sendEmail` project, Brevo, or OpenAI.
