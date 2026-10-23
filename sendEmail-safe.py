#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Send email without exposing the SMTP password in the process command line.

This program is intentionally compatible with Python 3.5.3 and later.
"""
from __future__ import print_function

import ctypes
import email.encoders
import email.header
import email.mime.application
import email.mime.base
import email.mime.image
import email.mime.multipart
import email.mime.text
import email.utils
import json
import sendemail_safe_profiles as profiles
import mimetypes
import os
import pwd
import resource
import smtplib
import ssl
import stat
import sys
import time

PROGRAM = 'sendEmail-safe.py'
VERSION = '1.2.1'
CONFIG_DIRNAME = profiles.NEW_CONFIG_DIR
SUPPORTED_MESSAGE_OPTIONS = {
    'fqdn',
    'message-charset',
    'message-content-type',
    'message-file',
    'reply-to',
    'timeout',
    'tls'
}


def fail(message, code=2):
    """Print an error and terminate."""
    print(PROGRAM + ': ' + message, file=sys.stderr)
    raise SystemExit(code)


def harden_process():
    """Disable core dumps and make the process non-dumpable where supported."""
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except Exception:
        pass

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE = 0 on Linux.
    except Exception:
        pass


def effective_home():
    """Return the home directory of the effective user."""
    try:
        return pwd.getpwuid(os.geteuid()).pw_dir
    except (KeyError, AttributeError):
        return os.path.expanduser('~')


def path_is_inside(path, directory):
    """Return True when path is directory itself or one of its descendants."""
    real_path = os.path.realpath(path)
    real_directory = os.path.realpath(directory)
    return (
        real_path == real_directory
        or real_path.startswith(real_directory + os.sep)
    )


def expand_effective_user_home(path):
    """Expand ~ using the effective user's home rather than the environment."""
    if not path:
        return path
    home = effective_home()
    if path == '~':
        return home
    if path.startswith('~/'):
        return os.path.join(home, path[2:])
    return path


def resolve_config(value):
    """Resolve a profile name/path, also accepting the legacy directory."""
    try:
        return profiles.resolve_config(value, home=effective_home())
    except ValueError as exc:
        fail(str(exc))


def load_config(path):
    """Load and validate a private, user-owned JSON configuration file."""
    flags = os.O_RDONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW

    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        fail('cannot open {}: {}'.format(path, exc))

    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            fail('{} is not a regular file'.format(path))
        if file_stat.st_uid != os.geteuid():
            fail('{} must be owned by the effective user'.format(path))

        mode = stat.S_IMODE(file_stat.st_mode)
        if mode & 0o077:
            fail(
                '{} must not be accessible by group or others; use chmod 600'.format(
                    path
                )
            )

        with os.fdopen(descriptor, 'r') as handle:
            descriptor = None
            try:
                config = json.load(handle)
            except ValueError as exc:
                fail('invalid JSON in {}: {}'.format(path, exc))
    finally:
        if descriptor is not None:
            os.close(descriptor)

    if not isinstance(config, dict):
        fail('profile must contain a JSON object')

    provider = config.get('provider', 'smtp')
    if provider == 'gmail_api':
        needed = ('from', 'oauth_client_id', 'oauth_refresh_token')
        missing = [
            name for name in needed
            if not isinstance(config.get(name), str) or not config.get(name)
        ]
        if missing:
            fail('missing Gmail API profile fields: ' + ', '.join(missing))
        try:
            config['timeout'] = float(config.get('timeout', 30))
        except (TypeError, ValueError):
            fail('invalid Gmail API timeout')
        if config['timeout'] <= 0:
            fail('Gmail API timeout must be positive')
        return config
    if provider != 'smtp':
        fail('unsupported provider: ' + str(provider))

    required = ('host', 'port', 'from', 'security')
    missing = [
        name for name in required
        if name not in config or config[name] in (None, '')
    ]
    if missing:
        fail('missing fields in {}: {}'.format(path, ', '.join(missing)))

    try:
        config['port'] = int(config['port'])
        config['timeout'] = float(config.get('timeout', 30))
    except (TypeError, ValueError):
        fail("the 'port' and 'timeout' fields must be numeric")

    if config['port'] < 1 or config['port'] > 65535:
        fail("the 'port' field must be between 1 and 65535")
    if config['timeout'] <= 0:
        fail("the 'timeout' field must be greater than zero")

    security = str(config.get('security', '')).lower()
    if security not in ('starttls', 'ssl', 'plain', 'auto'):
        fail(
            "invalid 'security' field: use starttls, ssl, plain, or auto"
        )
    config['security'] = security

    authentication = config.get('auth', True)
    if isinstance(authentication, str):
        authentication = authentication.lower() not in (
            'no', 'false', '0', 'off'
        )
    config['auth'] = bool(authentication)

    if config['auth']:
        auth_missing = [
            name for name in ('user', 'password')
            if name not in config or config[name] in (None, '')
        ]
        if auth_missing:
            fail(
                'authentication is enabled but fields are missing in {}: {}'.format(
                    path,
                    ', '.join(auth_missing)
                )
            )

    return config


def take_many(arguments, position):
    """Read one or more values following an option."""
    values = []
    position += 1
    while position < len(arguments) and not arguments[position].startswith('-'):
        values.append(arguments[position])
        position += 1
    return values, position


def print_help():
    print(
        'Usage: sendEmail-safe.py [-C PROFILE] -t TO... '
        '-u SUBJECT -m TEXT\n'
        '       [supported sendEmail-compatible options]\n\n'
        'Configuration:\n'
        '  -C, --config VALUE   Profile name or JSON path (optional)\n'
        '                       PROFILE resolves to\n'
        '                       ~/.config/sendEmail-safe/PROFILE.json\n'
        '                       Without it: unique profile, or unique -f match\n\n'
        'Message:\n'
        '  -f FROM              Envelope/header sender; profile default if omitted\n'
        '  -t TO...             Recipients\n'
        '  -cc TO...            Carbon-copy recipients\n'
        '  -bcc TO...           Blind-carbon-copy recipients\n'
        '  -u SUBJECT           Subject\n'
        '  -m TEXT              Message body\n'
        '  -a FILE...           Attachments\n'
        '  -l FILE              Log file; profile default if omitted\n'
        '  -q                   Suppress the success message\n'
        '  -v                   Print concise diagnostics, never SMTP AUTH traffic\n\n'
        'Compatibility overrides:\n'
        '  -s HOST:PORT         Override profile host and port\n'
        '  -xu USER             Override profile SMTP login\n'
        '  -o KEY=VALUE         Supported sendEmail-style option\n\n'
        'Supported -o keys:\n'
        '  fqdn, message-charset, message-content-type, message-file,\n'
        '  reply-to, timeout, tls\n\n'
        'The -xp option is deliberately rejected. The password is read only\n'
        'from the selected profile.\n'
    )


def parse(arguments):
    """Parse the supported sendEmail-compatible command-line subset."""
    data = {
        'config': None,
        'from': None,
        'to': [],
        'cc': [],
        'bcc': [],
        'subject': '',
        'body': '',
        'server': None,
        'user': None,
        'attachments': [],
        'log': None,
        'quiet': False,
        'verbose': False,
        'options': {}
    }

    position = 0
    while position < len(arguments):
        argument = arguments[position]

        if argument in ('-h', '--help'):
            print_help()
            raise SystemExit(0)

        if argument == '--version':
            print('{} {}'.format(PROGRAM, VERSION))
            raise SystemExit(0)

        if argument.startswith('--config='):
            data['config'] = argument.split('=', 1)[1]
            position += 1
            continue

        if argument in ('-C', '--config'):
            if position + 1 >= len(arguments):
                fail('missing value after ' + argument)
            data['config'] = arguments[position + 1]
            position += 2
            continue

        if argument == '-xp' or argument.startswith('-xp='):
            fail(
                'the -xp option is forbidden; store the password only in the '
                'selected profile'
            )

        if argument in ('-f', '-u', '-m', '-s', '-xu', '-l'):
            if position + 1 >= len(arguments):
                fail('missing value after ' + argument)
            value = arguments[position + 1]
            if argument == '-f':
                data['from'] = value
            elif argument == '-u':
                data['subject'] = value
            elif argument == '-m':
                data['body'] = value
            elif argument == '-s':
                data['server'] = value
            elif argument == '-xu':
                data['user'] = value
            elif argument == '-l':
                data['log'] = value
            position += 2
            continue

        if argument in ('-t', '-cc', '-bcc', '-a'):
            values, position = take_many(arguments, position)
            if not values:
                fail('missing value after ' + argument)
            key = {
                '-t': 'to',
                '-cc': 'cc',
                '-bcc': 'bcc',
                '-a': 'attachments'
            }[argument]
            data[key].extend(values)
            continue

        if argument == '-o':
            if position + 1 >= len(arguments):
                fail('missing value after -o')
            option = arguments[position + 1]
            key, separator, value = option.partition('=')
            key = key.lower()
            if key not in SUPPORTED_MESSAGE_OPTIONS:
                fail('unsupported -o option: ' + key)
            data['options'][key] = value if separator else 'yes'
            position += 2
            continue

        if argument == '-q':
            data['quiet'] = True
            position += 1
            continue

        if argument == '-v':
            data['verbose'] = True
            position += 1
            continue

        fail('unsupported option: ' + argument)

    return data


def addresses(items):
    """Extract normalized mailbox addresses from header-like input values."""
    return [address for _, address in email.utils.getaddresses(items) if address]


def resolve_server(value, config):
    """Return host and port, applying a compatible -s override when present."""
    host = config['host']
    port = config['port']
    if not value:
        return host, port
    if ':' in value:
        candidate_host, candidate_port = value.rsplit(':', 1)
        if candidate_port.isdigit():
            return candidate_host, int(candidate_port)
    return value, port


def load_message_file(path, charset):
    """Read a body file using the requested character set."""
    path = expand_effective_user_home(path)
    try:
        with open(path, 'rb') as handle:
            return handle.read().decode(charset, errors='replace')
    except OSError as exc:
        fail('cannot read message-file {}: {}'.format(path, exc))


def build_message(data, config):
    """Build a MIME message and return it with envelope addresses."""
    sender = (
        data['from']
        or config.get('from')
        or data['user']
        or config.get('user')
    )
    if not sender:
        fail('sender missing: use -f or configure the from field')

    recipients = addresses(data['to'] + data['cc'] + data['bcc'])
    if not recipients:
        fail('no recipients specified')

    options = data['options']
    charset = options.get('message-charset', 'utf-8')
    body = data['body']

    if options.get('message-file'):
        body = load_message_file(options['message-file'], charset)

    content_type = options.get('message-content-type', '').lower()
    subtype = 'html' if content_type == 'text/html' else 'plain'

    if data['attachments']:
        message = email.mime.multipart.MIMEMultipart()
        message.attach(
            email.mime.text.MIMEText(body, _subtype=subtype, _charset=charset)
        )
    else:
        message = email.mime.text.MIMEText(
            body,
            _subtype=subtype,
            _charset=charset
        )

    message['From'] = sender
    if data['to']:
        message['To'] = ', '.join(data['to'])
    if data['cc']:
        message['Cc'] = ', '.join(data['cc'])
    message['Subject'] = email.header.Header(
        data['subject'],
        charset
    ).encode()
    message['Date'] = email.utils.formatdate(localtime=True)
    message['Message-ID'] = email.utils.make_msgid()

    reply_to = options.get('reply-to') or config.get('reply_to')
    if reply_to:
        message['Reply-To'] = reply_to

    for original_path in data['attachments']:
        path = expand_effective_user_home(original_path)
        if not os.path.isfile(path):
            fail('attachment does not exist: ' + path)

        guessed_type, encoding = mimetypes.guess_type(path)
        if guessed_type is None or encoding is not None:
            guessed_type = 'application/octet-stream'
        main_type, sub_type = guessed_type.split('/', 1)

        with open(path, 'rb') as handle:
            payload = handle.read()

        if main_type == 'image':
            part = email.mime.image.MIMEImage(payload, _subtype=sub_type)
        elif main_type == 'application':
            part = email.mime.application.MIMEApplication(
                payload,
                _subtype=sub_type
            )
        else:
            part = email.mime.base.MIMEBase(main_type, sub_type)
            part.set_payload(payload)
            email.encoders.encode_base64(part)

        part.add_header(
            'Content-Disposition',
            'attachment',
            filename=('utf-8', '', os.path.basename(path))
        )
        message.attach(part)

    sender_address = email.utils.parseaddr(sender)[1] or sender
    return message, sender_address, recipients


def write_log(path, status, text):
    """Append a concise status line without message content or credentials."""
    if not path:
        return
    path = expand_effective_user_home(path)
    try:
        with open(path, 'a') as handle:
            handle.write('{} {} {}\n'.format(
                time.strftime('%F %T'),
                status,
                text.replace('\n', ' ')
            ))
    except OSError:
        pass


def tls_context(config):
    """Build the TLS context requested by the profile."""
    verify = config.get('tls_verify', True)
    if isinstance(verify, str):
        verify = verify.lower() not in ('no', 'false', '0', 'off')

    if not verify:
        return ssl._create_unverified_context()

    ca_file = config.get('ca_file') or None
    if ca_file:
        ca_file = expand_effective_user_home(ca_file)
        return ssl.create_default_context(cafile=ca_file)
    return ssl.create_default_context()


def main():
    harden_process()
    data = parse(sys.argv[1:])
    if data['config']:
        config_path = resolve_config(data['config'])
    else:
        try:
            config_path = profiles.choose_default_profile(
                sender=data['from'], home=effective_home()
            )
        except ValueError as exc:
            fail(str(exc))
    config = load_config(config_path)

    if config.get('provider') == 'gmail_api':
        # SMTP-only options must not silently change meaning for Gmail API.
        if data['server'] or data['user'] or any(
            key in data['options'] for key in ('tls', 'fqdn')
        ):
            fail('SMTP overrides are not supported with Gmail API profiles')
        try:
            timeout = float(
                data['options'].get('timeout', config.get('timeout', 30))
            )
        except (TypeError, ValueError):
            fail('invalid timeout')
        if timeout <= 0:
            fail('timeout must be greater than zero')
        message, sender_address, recipients = build_message(data, config)
        if data['bcc']:
            # Gmail API finds recipients in MIME headers, unlike SMTP envelope.
            message['Bcc'] = ', '.join(data['bcc'])
        log_path = data['log'] or config.get('log')
        try:
            from sendemail_safe_google import send_message
            send_message(message, config, timeout)
            write_log(log_path, 'OK', 'gmail_api recipients={}'.format(
                len(recipients)
            ))
            if not data['quiet']:
                print('Email sent through Gmail API using {}.'.format(
                    config_path
                ))
        except Exception as exc:
            write_log(log_path, 'ERROR', 'gmail_api {}'.format(
                type(exc).__name__
            ))
            fail('Gmail API delivery failed: {}: {}'.format(
                type(exc).__name__, exc
            ), 1)
        return

    host, port = resolve_server(data['server'], config)
    user = data['user'] or config.get('user')
    password = config.get('password')
    security = config['security']

    tls_option = data['options'].get('tls', '').lower()
    if tls_option in ('yes', 'true', '1', 'on'):
        security = 'ssl' if port == 465 else 'starttls'
    elif tls_option in ('no', 'false', '0', 'off'):
        security = 'plain'

    try:
        timeout = float(
            data['options'].get('timeout', config.get('timeout', 30))
        )
    except (TypeError, ValueError):
        fail('invalid timeout')
    if timeout <= 0:
        fail('timeout must be greater than zero')

    message, sender_address, recipients = build_message(data, config)
    log_path = data['log'] or config.get('log')
    context = tls_context(config)
    local_hostname = data['options'].get('fqdn') or None
    smtp = None

    if data['verbose']:
        print(
            '{}: profile={} server={}:{} security={} recipients={}'.format(
                PROGRAM,
                config_path,
                host,
                port,
                security,
                len(recipients)
            ),
            file=sys.stderr
        )

    try:
        if security == 'ssl' or port == 465:
            smtp = smtplib.SMTP_SSL(
                host,
                port,
                local_hostname=local_hostname,
                timeout=timeout,
                context=context
            )
        else:
            smtp = smtplib.SMTP(
                host,
                port,
                local_hostname=local_hostname,
                timeout=timeout
            )
            smtp.ehlo()
            if security in ('starttls', 'auto'):
                if security == 'starttls' or smtp.has_extn('starttls'):
                    smtp.starttls(context=context)
                    smtp.ehlo()
                elif security == 'starttls':
                    fail('the SMTP server does not offer STARTTLS', 1)

        if config.get('auth', True):
            smtp.login(user, password)

        smtp.sendmail(sender_address, recipients, message.as_string())
        write_log(
            log_path,
            'OK',
            '{}:{} recipients={}'.format(host, port, len(recipients))
        )

        if not data['quiet']:
            print(
                'Email sent through {}:{} using {}.'.format(
                    host,
                    port,
                    config_path
                )
            )

    except SystemExit:
        raise
    except Exception as exc:
        write_log(
            log_path,
            'ERROR',
            '{}: {}'.format(type(exc).__name__, exc)
        )
        fail(
            'delivery failed: {}: {}'.format(type(exc).__name__, exc),
            1
        )
    finally:
        password = None
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                try:
                    smtp.close()
                except Exception:
                    pass


if __name__ == '__main__':
    main()
