#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create or update per-user sendEmail-safe SMTP profiles.

This program is intentionally compatible with Python 3.5.3 and later.
"""
from __future__ import print_function

import argparse
import getpass
import json
import os
import pwd
import stat
import tempfile

PROGRAM = 'sendEmail-safe-configure.py'
VERSION = '1.0.0'
CONFIG_DIRNAME = os.path.join('.config', 'sendemail-safe')


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


def resolve_config(value):
    """Resolve a profile name or explicit path inside the effective user's home."""
    home = effective_home()
    config_root = os.path.join(home, CONFIG_DIRNAME)

    if value == '~':
        candidate = home
    elif value.startswith('~/'):
        candidate = os.path.join(home, value[2:])
    elif os.path.isabs(value):
        candidate = value
    elif '/' in value or value.startswith('.'):
        candidate = os.path.abspath(value)
    else:
        filename = value if value.endswith('.json') else value + '.json'
        candidate = os.path.join(config_root, filename)

    candidate = os.path.realpath(candidate)
    if not path_is_inside(candidate, home):
        raise SystemExit(
            '{}: the file must be inside {}'.format(PROGRAM, home)
        )
    return candidate


def ask(label, default=''):
    """Prompt for a text value, preserving a non-empty default on Enter."""
    if default not in (None, ''):
        prompt = '{} [{}]: '.format(label, default)
    else:
        prompt = '{}: '.format(label)
    value = input(prompt).strip()
    return value or default


def ask_bool(label, default=True):
    """Prompt for a yes/no value."""
    default_text = 'y' if default else 'n'
    while True:
        value = input(
            '{} [y/n, default={}]: '.format(label, default_text)
        ).strip().lower()
        if not value:
            return default
        if value in ('y', 'yes'):
            return True
        if value in ('n', 'no'):
            return False
        print('Please answer y or n.')


def load_existing(path):
    """Load an existing private profile owned by the effective user."""
    if not os.path.exists(path):
        return {}

    file_stat = os.stat(path)
    if not stat.S_ISREG(file_stat.st_mode):
        raise SystemExit('{}: {} is not a regular file'.format(PROGRAM, path))
    if file_stat.st_uid != os.geteuid():
        raise SystemExit(
            '{}: {} is not owned by the effective user'.format(PROGRAM, path)
        )
    if stat.S_IMODE(file_stat.st_mode) & 0o077:
        raise SystemExit(
            '{}: {} has unsafe permissions; use chmod 600'.format(
                PROGRAM,
                path
            )
        )

    try:
        with open(path, 'r') as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise SystemExit(
            '{}: invalid existing configuration: {}'.format(PROGRAM, exc)
        )


def ensure_private_directory(path):
    """Create the profile directory and restrict the final directory to 0700."""
    if not os.path.isdir(path):
        os.makedirs(path, 0o700)
    os.chmod(path, 0o700)


def prompt_port(existing):
    """Prompt until a valid TCP port is entered."""
    while True:
        try:
            port = int(ask('SMTP port', str(existing.get('port', 587))))
            if port < 1 or port > 65535:
                raise ValueError()
            return port
        except ValueError:
            print('Invalid port. Enter a number between 1 and 65535.')


def prompt_timeout(existing):
    """Prompt until a positive timeout is entered."""
    while True:
        value = ask('Timeout in seconds', str(existing.get('timeout', 30)))
        try:
            timeout = float(value)
            if timeout <= 0:
                raise ValueError()
            return timeout
        except ValueError:
            print('Invalid timeout. Enter a positive number.')


def prompt_security(existing):
    """Prompt until a supported transport security mode is entered."""
    while True:
        security = ask(
            'Security mode (starttls/ssl/plain/auto)',
            existing.get('security', 'starttls')
        ).lower()
        if security in ('starttls', 'ssl', 'plain', 'auto'):
            return security
        print('Invalid value. Use starttls, ssl, plain, or auto.')


def prompt_password(existing, authentication):
    """Prompt for a new password or preserve the existing one."""
    if not authentication:
        return ''

    if existing.get('password'):
        password = getpass.getpass(
            'New SMTP password/key (Enter keeps the current value): '
        )
        if not password:
            return existing['password']
        confirmation = getpass.getpass('Repeat the new SMTP password/key: ')
    else:
        password = getpass.getpass('SMTP password/key: ')
        confirmation = getpass.getpass('Repeat the SMTP password/key: ')
        if not password:
            raise SystemExit('{}: the password must not be empty'.format(PROGRAM))

    if password != confirmation:
        raise SystemExit('{}: the passwords do not match'.format(PROGRAM))
    return password


def main():
    parser = argparse.ArgumentParser(
        description='Create an SMTP profile in the effective user\'s home.'
    )
    parser.add_argument(
        '-C',
        '--config',
        required=True,
        help='profile name or path inside the effective user\'s home'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='{} {}'.format(PROGRAM, VERSION)
    )
    args = parser.parse_args()

    path = resolve_config(args.config)
    directory = os.path.dirname(path)
    ensure_private_directory(directory)
    existing = load_existing(path)

    host = ask('SMTP server', existing.get('host', 'smtp-relay.brevo.com'))
    port = prompt_port(existing)
    authentication = ask_bool(
        'Use SMTP authentication',
        bool(existing.get('auth', True))
    )

    user = ''
    if authentication:
        user = ask('SMTP login', existing.get('user', ''))
        if not user:
            raise SystemExit(
                '{}: SMTP login is required when authentication is enabled'.format(
                    PROGRAM
                )
            )

    sender_default = existing.get('from', user)
    sender = ask('Default sender', sender_default)
    if not sender:
        raise SystemExit('{}: the default sender must not be empty'.format(PROGRAM))

    security = prompt_security(existing)
    timeout = prompt_timeout(existing)
    tls_verify = ask_bool(
        'Verify the TLS certificate',
        bool(existing.get('tls_verify', True))
    )
    ca_file = ask(
        'Custom CA file (empty = system trust store)',
        existing.get('ca_file', '')
    )
    log_file = ask(
        'Default log file (empty = no log)',
        existing.get('log', '')
    )
    reply_to = ask(
        'Default Reply-To (empty = none)',
        existing.get('reply_to', '')
    )
    password = prompt_password(existing, authentication)

    data = {
        'auth': authentication,
        'from': sender,
        'host': host,
        'password': password,
        'port': port,
        'security': security,
        'timeout': timeout,
        'tls_verify': tls_verify,
        'user': user
    }
    if ca_file:
        data['ca_file'] = ca_file
    if log_file:
        data['log'] = log_file
    if reply_to:
        data['reply_to'] = reply_to

    descriptor, temporary = tempfile.mkstemp(
        prefix='.sendemail-safe.',
        suffix='.tmp',
        dir=directory,
        text=True
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, 'w') as handle:
            descriptor = None
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if os.path.exists(temporary):
            os.unlink(temporary)

    password = None
    print('Profile written to {} with mode 0600.'.format(path))
    print('Usage: sendEmail-safe.py --config {} ...'.format(args.config))


if __name__ == '__main__':
    main()
