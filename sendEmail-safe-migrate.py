#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Migrate shell commands from sendEmail to sendEmail-safe.py.

This program is intentionally compatible with Python 3.5.3 and later.
"""
from __future__ import print_function

import argparse
import os
import pwd
import re
import shlex
import subprocess
import sys
import tarfile
import time

PROGRAM = 'sendEmail-safe-migrate.py'
VERSION = '1.1.0'
NEW_COMMAND = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'sendEmail-safe.py'
)
EXCLUDED_DIRECTORIES = {
    '.git',
    '.hg',
    '.svn',
    '.venv',
    '__pycache__',
    'node_modules',
    'venv'
}
SHELL_EXTENSIONS = ('.sh', '.bash', '.dash', '.ksh', '.zsh')
COMMAND_PATTERN = re.compile(
    r'(?<![A-Za-z0-9_./-])'
    r'(?P<command>'
    r'(?:(?:/usr/bin|/usr/local/bin)/)?'
    r'(?:sendEmail|sendEmail-safe(?:\.py)?)'
    r')'
    r'(?=(?:[ \t]|\\\n|$))'
)


def effective_home():
    """Return the home directory of the effective user."""
    try:
        return pwd.getpwuid(os.geteuid()).pw_dir
    except (KeyError, AttributeError):
        return os.path.expanduser('~')


def files_under(roots):
    """Yield regular, non-symlink files below the supplied roots."""
    for root in roots:
        if not os.path.exists(root):
            print('WARNING: path does not exist: ' + root, file=sys.stderr)
            continue
        if os.path.isfile(root) and not os.path.islink(root):
            yield root
            continue

        for directory, directories, files in os.walk(
            root,
            topdown=True,
            followlinks=False
        ):
            directories[:] = [
                name for name in directories
                if name not in EXCLUDED_DIRECTORIES
                and not os.path.islink(os.path.join(directory, name))
            ]
            for name in files:
                path = os.path.join(directory, name)
                if os.path.isfile(path) and not os.path.islink(path):
                    yield path


def read_text(path):
    """Read a text file while preserving non-UTF-8 bytes losslessly."""
    with open(path, 'rb') as handle:
        raw = handle.read()
    if b'\x00' in raw:
        return None, raw
    return raw.decode('utf-8', errors='surrogateescape'), raw


def shell_file(path, raw):
    """Recognize shell scripts by extension or shebang."""
    if path.lower().endswith(SHELL_EXTENSIONS):
        return True
    first_line = raw.split(b'\n', 1)[0].lower()
    return first_line.startswith(b'#!') and any(
        value in first_line
        for value in (b'/sh', b'/bash', b'/dash', b'/ksh', b'/zsh')
    )


def command_matches(text):
    """Yield sendEmail command matches outside shell quotes and comments.

    This is a conservative lexical scan, not a complete shell parser. It avoids
    changing command names embedded in ordinary quoted strings or comments.
    """
    position = 0
    quote = None
    escaped = False
    comment = False

    while position < len(text):
        character = text[position]

        if comment:
            if character == '\n':
                comment = False
            position += 1
            continue

        if quote == "'":
            if character == "'":
                quote = None
            position += 1
            continue

        if quote == '"':
            if escaped:
                escaped = False
                position += 1
                continue
            if character == '\\':
                escaped = True
                position += 1
                continue
            if character == '"':
                quote = None
            position += 1
            continue

        if escaped:
            escaped = False
            position += 1
            continue

        if character == '\\':
            escaped = True
            position += 1
            continue
        if character in ("'", '"'):
            quote = character
            position += 1
            continue
        if character == '#' and (
            position == 0
            or text[position - 1].isspace()
            or text[position - 1] in ';|&()'
        ):
            comment = True
            position += 1
            continue

        match = COMMAND_PATTERN.match(text, position)
        if match is not None:
            yield match
            position = match.end()
            continue

        position += 1


def command_end(text, start):
    """Find the end of one shell command beginning at start."""
    position = start
    quote = None
    escaped = False
    command_substitution_depth = 0
    parameter_depth = 0

    while position < len(text):
        character = text[position]

        if quote == "'":
            if character == "'":
                quote = None
            position += 1
            continue

        if quote == '"':
            if escaped:
                escaped = False
                position += 1
                continue
            if character == '\\':
                escaped = True
                position += 1
                continue
            if character == '"':
                quote = None
                position += 1
                continue
            if text.startswith('$(', position):
                command_substitution_depth += 1
                position += 2
                continue
            if text.startswith('${', position):
                parameter_depth += 1
                position += 2
                continue
            if character == ')' and command_substitution_depth:
                command_substitution_depth -= 1
            elif character == '}' and parameter_depth:
                parameter_depth -= 1
            position += 1
            continue

        if escaped:
            escaped = False
            position += 1
            continue

        if character == '\\':
            if position + 1 < len(text) and text[position + 1] == '\n':
                position += 2
            else:
                escaped = True
                position += 1
            continue

        if character in ("'", '"'):
            quote = character
            position += 1
            continue

        if text.startswith('$(', position):
            command_substitution_depth += 1
            position += 2
            continue
        if text.startswith('${', position):
            parameter_depth += 1
            position += 2
            continue
        if character == ')' and command_substitution_depth:
            command_substitution_depth -= 1
            position += 1
            continue
        if character == '}' and parameter_depth:
            parameter_depth -= 1
            position += 1
            continue

        if command_substitution_depth == 0 and parameter_depth == 0:
            if character in '\n;|&':
                return position
            if character == '#' and (
                position == start or text[position - 1].isspace()
            ):
                return position

        position += 1

    return len(text)


def shell_tokens(command):
    """Return shell word spans while respecting quotes and escapes."""
    tokens = []
    position = 0

    while position < len(command):
        while position < len(command):
            if command.startswith('\\\n', position):
                position += 2
            elif command[position].isspace():
                position += 1
            else:
                break

        if position >= len(command):
            break
        if command[position] == '#':
            break

        start = position
        quote = None
        escaped = False
        command_substitution_depth = 0
        parameter_depth = 0

        while position < len(command):
            character = command[position]

            if quote == "'":
                position += 1
                if character == "'":
                    quote = None
                continue

            if quote == '"':
                if escaped:
                    escaped = False
                    position += 1
                    continue
                if character == '\\':
                    escaped = True
                    position += 1
                    continue
                if character == '"':
                    quote = None
                    position += 1
                    continue
                if command.startswith('$(', position):
                    command_substitution_depth += 1
                    position += 2
                    continue
                if command.startswith('${', position):
                    parameter_depth += 1
                    position += 2
                    continue
                if character == ')' and command_substitution_depth:
                    command_substitution_depth -= 1
                elif character == '}' and parameter_depth:
                    parameter_depth -= 1
                position += 1
                continue

            if escaped:
                escaped = False
                position += 1
                continue

            if character == '\\':
                if position + 1 < len(command) and command[position + 1] == '\n':
                    position += 2
                else:
                    escaped = True
                    position += 1
                continue

            if character in ("'", '"'):
                quote = character
                position += 1
                continue
            if command.startswith('$(', position):
                command_substitution_depth += 1
                position += 2
                continue
            if command.startswith('${', position):
                parameter_depth += 1
                position += 2
                continue
            if character == ')' and command_substitution_depth:
                command_substitution_depth -= 1
                position += 1
                continue
            if character == '}' and parameter_depth:
                parameter_depth -= 1
                position += 1
                continue

            if (
                command_substitution_depth == 0
                and parameter_depth == 0
                and character.isspace()
            ):
                break

            position += 1

        tokens.append((start, position, command[start:position]))

    return tokens


def token_value(raw_token):
    """Decode a single shell token when possible."""
    try:
        values = shlex.split(raw_token, posix=True)
    except ValueError:
        return raw_token
    if len(values) == 1:
        return values[0]
    return raw_token


def removal_span(command, option_start, value_end):
    """Choose a clean text span for removing an option and its value."""
    line_start = command.rfind('\n', 0, option_start) + 1
    line_end = command.find('\n', value_end)
    if line_end < 0:
        line_end = len(command)
        newline_end = line_end
    else:
        newline_end = line_end + 1

    prefix = command[line_start:option_start]
    suffix = command[value_end:line_end]
    if prefix.strip() == '' and re.match(r'^[ \t]*(?:\\)?[ \t]*$', suffix):
        return line_start, newline_end

    start = option_start
    while start > 0 and command[start - 1] in ' \t':
        start -= 1
    return start, value_end


def remove_selected_options(command, remove_overrides):
    """Remove credential and selected SMTP override options from one command."""
    tokens = shell_tokens(command)
    spans = []
    counts = {
        'passwords': 0,
        'servers': 0,
        'users': 0,
        'tls_options': 0
    }

    position = 1
    while position < len(tokens):
        start, end, raw = tokens[position]
        value = token_value(raw)

        if value in ('-xp', '-s', '-xu', '-o') and position + 1 < len(tokens):
            next_start, next_end, next_raw = tokens[position + 1]
            next_value = token_value(next_raw)
            remove = False
            counter = None

            if value == '-xp':
                remove = True
                counter = 'passwords'
            elif remove_overrides and value == '-s':
                remove = True
                counter = 'servers'
            elif remove_overrides and value == '-xu':
                remove = True
                counter = 'users'
            elif (
                remove_overrides
                and value == '-o'
                and next_value.lower().startswith('tls=')
            ):
                remove = True
                counter = 'tls_options'

            if remove:
                spans.append(removal_span(command, start, next_end))
                counts[counter] += 1
                position += 2
                continue

        if value.startswith('-xp='):
            spans.append(removal_span(command, start, end))
            counts['passwords'] += 1

        position += 1

    if not spans:
        return command, counts

    spans.sort()
    output = []
    cursor = 0
    for start, end in spans:
        if start < cursor:
            continue
        output.append(command[cursor:start])
        cursor = end
    output.append(command[cursor:])
    return ''.join(output), counts


def cleanup_command(command):
    """Remove empty continuation lines and a dangling final backslash."""
    command = re.sub(r'\n[ \t]*\\[ \t]*(?=\n|$)', '\n', command)
    command = re.sub(r'[ \t]*\\[ \t]*$', '', command)
    return command.rstrip(' \t')


def command_has_config(command):
    """Return True if a safe command already specifies -C or --config."""
    tokens = shell_tokens(command)
    for _, _, raw in tokens[1:]:
        value = token_value(raw)
        if value in ('-C', '--config') or value.startswith('--config='):
            return True
    return False


def command_is_old(raw_command):
    """Return True for the original sendEmail executable."""
    return os.path.basename(raw_command) == 'sendEmail'


def transform_command(command, config_value, keep_overrides):
    """Transform one sendEmail command and return statistics."""
    tokens = shell_tokens(command)
    statistics = {
        'old_commands': 0,
        'safe_without_config': 0,
        'passwords': 0,
        'servers': 0,
        'users': 0,
        'tls_options': 0
    }
    if not tokens:
        return command, statistics

    command_start, command_end_position, raw_command = tokens[0]
    quoted_config = shlex.quote(config_value)

    if command_is_old(token_value(raw_command)):
        replacement = '{} --config {}'.format(NEW_COMMAND, quoted_config)
        command = (
            command[:command_start]
            + replacement
            + command[command_end_position:]
        )
        statistics['old_commands'] = 1
    else:
        normalized = NEW_COMMAND
        command = (
            command[:command_start]
            + normalized
            + command[command_end_position:]
        )
        if not command_has_config(command):
            insertion = ' --config {}'.format(quoted_config)
            command = (
                command[:command_start + len(normalized)]
                + insertion
                + command[command_start + len(normalized):]
            )
            statistics['safe_without_config'] = 1

    command, removed = remove_selected_options(
        command,
        remove_overrides=not keep_overrides
    )
    command = cleanup_command(command)
    for key in removed:
        statistics[key] += removed[key]
    return command, statistics


def migrate_text(text, config_value, keep_overrides=False):
    """Migrate all executable command occurrences in a text string."""
    matches = list(command_matches(text))
    if not matches:
        return text, {
            'old_commands': 0,
            'safe_without_config': 0,
            'passwords': 0,
            'servers': 0,
            'users': 0,
            'tls_options': 0
        }

    totals = {
        'old_commands': 0,
        'safe_without_config': 0,
        'passwords': 0,
        'servers': 0,
        'users': 0,
        'tls_options': 0
    }
    output = []
    cursor = 0

    for match in matches:
        if match.start() < cursor:
            continue
        end = command_end(text, match.start())
        original = text[match.start():end]
        changed, statistics = transform_command(
            original,
            config_value,
            keep_overrides
        )
        output.append(text[cursor:match.start()])
        output.append(changed)
        cursor = end
        for key in totals:
            totals[key] += statistics[key]

    output.append(text[cursor:])
    return ''.join(output), totals


def sum_stat(candidates, key):
    """Sum a named migration statistic."""
    return sum(item['statistics'][key] for item in candidates)


def safe_archive_name(path, base_directory):
    """Return a relative archive name without leading parent traversals."""
    absolute = os.path.abspath(path)
    base = os.path.abspath(base_directory)
    if absolute == base or absolute.startswith(base + os.sep):
        return os.path.relpath(absolute, base)
    return os.path.join('external-files', os.path.basename(path))


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Replace sendEmail with sendEmail-safe.py and remove command-line '
            'SMTP passwords from shell scripts.'
        )
    )
    parser.add_argument(
        '-C',
        '--config',
        required=True,
        help='profile name or path inserted into each migrated command'
    )
    parser.add_argument(
        '--keep-smtp-overrides',
        action='store_true',
        help='keep -s, -xu, and -o tls=... in migrated commands'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='apply changes without an interactive confirmation prompt'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='{} {}'.format(PROGRAM, VERSION)
    )
    parser.add_argument(
        'roots',
        nargs='*',
        default=['adminscript', 'userscript'],
        help='files or directories to inspect'
    )
    args = parser.parse_args()

    candidates = []

    for path in files_under(args.roots):
        try:
            text, raw = read_text(path)
        except OSError as exc:
            print('UNREADABLE {}: {}'.format(path, exc), file=sys.stderr)
            continue

        if text is None or not shell_file(path, raw):
            continue
        if 'sendEmail' not in text:
            continue

        changed, statistics = migrate_text(
            text,
            args.config,
            keep_overrides=args.keep_smtp_overrides
        )
        if changed != text:
            candidates.append({
                'path': path,
                'original': raw,
                'replacement': changed.encode(
                    'utf-8',
                    errors='surrogateescape'
                ),
                'statistics': statistics
            })

    print('Profile inserted: {}'.format(args.config))
    print('Files to modify: {}'.format(len(candidates)))
    print('sendEmail commands replaced: {}'.format(
        sum_stat(candidates, 'old_commands')
    ))
    print('Existing safe commands completed with --config: {}'.format(
        sum_stat(candidates, 'safe_without_config')
    ))
    print('-xp options removed: {}'.format(
        sum_stat(candidates, 'passwords')
    ))
    print('-s options removed: {}'.format(
        sum_stat(candidates, 'servers')
    ))
    print('-xu options removed: {}'.format(
        sum_stat(candidates, 'users')
    ))
    print('-o tls=... options removed: {}'.format(
        sum_stat(candidates, 'tls_options')
    ))

    for item in candidates:
        statistics = item['statistics']
        print(
            '  {}  sendEmail={}  safe-without-config={}  -xp={}  '
            '-s={}  -xu={}  tls={}'.format(
                item['path'],
                statistics['old_commands'],
                statistics['safe_without_config'],
                statistics['passwords'],
                statistics['servers'],
                statistics['users'],
                statistics['tls_options']
            )
        )

    if not candidates:
        raise SystemExit('No changes are required.')

    if not args.yes:
        answer = input('\nCreate a backup and apply the changes? [y/N] ')
        if answer.strip().lower() not in ('y', 'yes'):
            raise SystemExit('Operation cancelled.')

    backup_directory = os.path.join(
        effective_home(),
        '.local',
        'state',
        'sendemail-safe-backups'
    )
    if not os.path.isdir(backup_directory):
        os.makedirs(backup_directory)
    os.chmod(backup_directory, 0o700)

    backup = os.path.join(
        backup_directory,
        'migration-{}.tar.gz'.format(time.strftime('%Y%m%d_%H%M%S'))
    )

    working_directory = os.getcwd()
    old_umask = os.umask(0o077)
    try:
        with tarfile.open(backup, 'w:gz') as archive:
            for item in candidates:
                archive.add(
                    item['path'],
                    arcname=safe_archive_name(
                        item['path'],
                        working_directory
                    ),
                    recursive=False
                )
    finally:
        os.umask(old_umask)
    os.chmod(backup, 0o600)

    modified = []
    for item in candidates:
        with open(item['path'], 'r+b') as handle:
            handle.seek(0)
            handle.write(item['replacement'])
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
        modified.append(item['path'])

    failed = False
    for path in modified:
        text, raw = read_text(path)
        for match in command_matches(text):
            end = command_end(text, match.start())
            command = text[match.start():end]
            for _, _, raw_token in shell_tokens(command):
                value = token_value(raw_token)
                if value == '-xp' or value.startswith('-xp='):
                    print('ERROR: -xp remains in ' + path)
                    failed = True

        result = subprocess.run(
            ['bash', '-n', path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        if result.returncode != 0:
            print(
                'ERROR: bash -n failed for {}: {}'.format(
                    path,
                    result.stderr.strip()
                )
            )
            failed = True

    print('\nBackup: ' + backup)
    print('Files modified: {}'.format(len(modified)))
    if failed:
        raise SystemExit(1)
    print('Validation completed: no -xp remains and shell syntax is valid.')
    print('Review the diff before committing the migrated scripts.')


if __name__ == '__main__':
    main()
