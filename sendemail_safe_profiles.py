#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safe, deterministic per-user profile naming and legacy lookup.

The default directory is case-sensitive: ~/.config/sendEmail-safe/.
The legacy ~/.config/sendemail-safe/ remains readable, without moving secrets.
Python 3.5+ standard library only.
"""
from __future__ import print_function

import json
import os
import pwd
import re
import stat
import unicodedata


NEW_CONFIG_DIR = os.path.join('.config', 'sendEmail-safe')
LEGACY_CONFIG_DIR = os.path.join('.config', 'sendemail-safe')
MAX_STEM_LENGTH = 180


def effective_home():
    """Use the effective uid to avoid relying on a spoofed HOME."""
    return pwd.getpwuid(os.geteuid()).pw_dir


def inside_home(path, home):
    real_path = os.path.realpath(path)
    real_home = os.path.realpath(home)
    return real_path == real_home or real_path.startswith(real_home + os.sep)


def detox_ascii(value):
    """NFKD transliteration, only [a-z0-9_], collapsing separators.

    Equivalent in spirit to 'detox', but deterministic without an external
    dependency. It is not injective; callers must guard filename collisions.
    """
    if not isinstance(value, str):
        raise ValueError('profile identifier must be a string')
    normal = unicodedata.normalize('NFKD', value)
    basic = normal.encode('ascii', 'ignore').decode('ascii').lower()
    stem = re.sub(r'[^a-z0-9]+', '_', basic).strip('_')
    if not stem:
        raise ValueError('login or server has no ASCII alphanumeric characters')
    return stem


def profile_filename(login, server):
    """Use the whole login and server in the stem where possible."""
    login_part = detox_ascii(login.strip())
    server_part = detox_ascii(server.strip())
    stem = login_part + '_' + server_part
    if len(stem) > MAX_STEM_LENGTH:
        import hashlib
        digest = hashlib.sha256(
            (login + '\0' + server).encode('utf-8')
        ).hexdigest()[:12]
        stem = stem[:MAX_STEM_LENGTH - 13].rstrip('_') + '_' + digest
    return stem + '.json'


def default_profile_path(login, server, home=None):
    home = home or effective_home()
    return os.path.join(
        home, NEW_CONFIG_DIR, profile_filename(login, server)
    )


def resolve_config(value, home=None, allow_legacy=True):
    """Resolve --config NAME|PATH; simple names default to the new directory.

    Explicit paths must be under the effective user's home. If a simple name
    is absent from the new directory, try the old directory for compatibility.
    """
    if not value:
        raise ValueError('profile name or path is required')
    home = home or effective_home()
    if value == '~':
        candidate = home
    elif value.startswith('~/'):
        candidate = os.path.join(home, value[2:])
    elif os.path.isabs(value):
        candidate = value
    elif '/' in value or value.startswith('.'):
        candidate = os.path.abspath(value)
    else:
        name = value if value.endswith('.json') else value + '.json'
        candidate = os.path.join(home, NEW_CONFIG_DIR, name)
        if allow_legacy and not os.path.lexists(candidate):
            old = os.path.join(home, LEGACY_CONFIG_DIR, name)
            if os.path.lexists(old):
                candidate = old
    candidate = os.path.realpath(candidate)
    if not inside_home(candidate, home):
        raise ValueError('profile path must be inside ' + home)
    return candidate


def private_profile_identity(path):
    """Read identity fields from an existing profile with safe permissions.

    Called before an overwrite to prevent silent collisions in detox names.
    """
    flags = os.O_RDONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            raise ValueError('existing profile is not a user-owned regular file')
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError('existing profile permissions must be 0600')
        with os.fdopen(descriptor, 'r') as handle:
            descriptor = None
            data = json.load(handle)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if data.get('provider') == 'gmail_api':
        return (data.get('from', '').strip().lower(), 'gmail.googleapis.com')
    return (
        (data.get('user') or data.get('from') or '').strip().lower(),
        (data.get('host') or '').strip().lower()
    )


def verify_no_collision(path, login, server):
    """Never overwrite a generated name that belongs to another identity."""
    if os.path.lexists(path):
        actual = private_profile_identity(path)
        wanted = (login.strip().lower(), server.strip().lower())
        if actual != wanted:
            raise ValueError(
                'normalized profile filename collides with an existing '
                'account; use --config NAME or --config PATH'
            )


def choose_default_profile(sender=None, home=None):
    """Select the sole safe profile, optionally disambiguated by -f.

    Never guess an account when multiple eligible profiles exist.
    Does not parse or expose secrets when listing candidates.
    """
    home = home or effective_home()
    candidates = []
    for dirname in (NEW_CONFIG_DIR, LEGACY_CONFIG_DIR):
        folder = os.path.join(home, dirname)
        if not os.path.isdir(folder) or os.path.islink(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith('.json'):
                continue
            path = os.path.join(folder, name)
            try:
                info = os.lstat(path)
                if not stat.S_ISREG(info.st_mode):
                    continue
                if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
                    continue
                candidates.append(path)
            except OSError:
                continue
    if sender:
        matched = []
        for path in candidates:
            try:
                # Read safely but only use sender identity; no secrets logged.
                flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                fd = os.open(path, flags)
                with os.fdopen(fd, 'r') as f:
                    data = json.load(f)
                if data.get('from', '').strip().lower() == sender.strip().lower():
                    matched.append(path)
            except (OSError, ValueError, TypeError, AttributeError):
                continue
        candidates = matched
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError(
            'no matching profile; configure one or specify --config NAME|PATH'
        )
    raise ValueError(
        'multiple profiles available; specify --config NAME|PATH'
    )
