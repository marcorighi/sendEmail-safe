#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Authorize a personal Gmail profile using OAuth 2.0 PKCE and loopback.

Run as the mail-sending user, not root. Python 3.5+ standard library only.
"""
from __future__ import print_function

import argparse
import base64
import hashlib
import http.server
import json
import os
import re
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import sendemail_safe_profiles as profiles


AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
SCOPE = 'https://www.googleapis.com/auth/gmail.send'


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def read_client(path):
    with open(path, 'r') as handle:
        data = json.load(handle)
    client = data.get('installed')
    if not isinstance(client, dict) or not client.get('client_id'):
        raise ValueError('expected Google OAuth Desktop app client JSON')
    return client


def build_auth_url(client_id, redirect_uri, verifier, state):
    challenge = b64url(hashlib.sha256(verifier.encode('ascii')).digest())
    values = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent',
        'scope': SCOPE,
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256'
    }
    return AUTH_URL + '?' + urllib.parse.urlencode(values)


def exchange_code(client, code, redirect_uri, verifier):
    fields = {
        'client_id': client['client_id'],
        'client_secret': client.get('client_secret', ''),
        'code': code,
        'redirect_uri': redirect_uri,
        'code_verifier': verifier,
        'grant_type': 'authorization_code'
    }
    request = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(fields).encode('ascii'),
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise ValueError('OAuth authorization failed (HTTP {})'.format(exc.code))
    token = result.get('refresh_token')
    if not isinstance(token, str) or not token:
        raise ValueError(
            'No refresh token returned. Verify offline consent and OAuth '
            'client configuration, then authorize again.'
        )
    scope = result.get('scope', SCOPE).split()
    if SCOPE not in scope:
        raise ValueError('Google did not grant gmail.send permission')
    return token


def profile_destination(name, address):
    """Resolve the new path without writing a profile."""
    home = profiles.effective_home()
    if name:
        if '/' not in name and not re.match(r'^[A-Za-z0-9_-]+$', name):
            raise ValueError('profile name: use ASCII letters, digits, _ or -')
        return profiles.resolve_config(
            name, home=home, allow_legacy=True
        )
    return profiles.default_profile_path(
        address, 'gmail.googleapis.com', home=home
    )


def save_profile(name, address, client, refresh_token):
    path = profile_destination(name, address)
    directory = os.path.dirname(path)
    if os.path.islink(directory):
        raise ValueError('profile directory must not be a symlink')
    if not os.path.isdir(directory):
        os.makedirs(directory, mode=0o700)
    os.chmod(directory, 0o700)
    if not name:
        profiles.verify_no_collision(
            path, address, 'gmail.googleapis.com'
        )
    if os.path.lexists(path):
        raise ValueError('profile already exists: ' + path)

    profile = {
        'provider': 'gmail_api',
        'from': address,
        'oauth_client_id': client['client_id'],
        'oauth_client_secret': client.get('client_secret', ''),
        'oauth_refresh_token': refresh_token,
        'timeout': 30.0
    }
    descriptor, temporary = tempfile.mkstemp(
        prefix='.gmail-oauth-', suffix='.tmp', dir=directory
    )
    try:
        os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, 'w') as handle:
            json.dump(profile, handle, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        # Hard-link creation fails when a file appears concurrently,
        # preventing inadvertent overwrites even in that race.
        os.link(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def receive_code(client_id, verifier, state, timeout):
    result = {'code': None, 'error': None}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format_string, *args):
            # Do not log the OAuth authorization code from the URL.
            return

        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            accepted = (
                parsed.path == '/oauth2/callback' and
                query.get('state', [''])[0] == state
            )
            if accepted:
                if 'error' in query:
                    result['error'] = 'OAuth authorization was declined'
                else:
                    result['code'] = query.get('code', [None])[0]
                    if not result['code']:
                        result['error'] = 'OAuth response contained no code'
            self.send_response(200 if accepted else 400)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(
                (b'Authorization received. You may close this page.'
                 if accepted else b'Invalid authorization response.')
            )

    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    server.timeout = 1
    redirect_uri = 'http://127.0.0.1:{}/oauth2/callback'.format(server.server_port)
    url = build_auth_url(client_id, redirect_uri, verifier, state)
    try:
        print('Opening the system browser for Google authorization.')
        print('If it does not open, visit this URL in the same computer:')
        print(url)
        webbrowser.open(url)
        deadline = time.time() + timeout
        while result['code'] is None and result['error'] is None:
            if time.time() >= deadline:
                raise ValueError('timed out waiting for browser authorization')
            server.handle_request()
    finally:
        server.server_close()
    if result['error']:
        raise ValueError(result['error'])
    return result['code'], redirect_uri


def main():
    parser = argparse.ArgumentParser(
        description='Create a Gmail API OAuth 2.0 profile (gmail.send only).'
    )
    parser.add_argument('--config', help='Optional profile name or path')
    parser.add_argument('--from', dest='sender', required=True, help='Gmail sender')
    parser.add_argument(
        '--client-secrets', required=True,
        help='Google OAuth Desktop client JSON downloaded from Google Cloud'
    )
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()

    if os.geteuid() == 0:
        parser.error('run as the account owner, not root')
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    if not args.sender or '\n' in args.sender or '\r' in args.sender:
        parser.error('invalid sender address')
    destination = profile_destination(args.config, args.sender)
    if os.path.lexists(destination):
        parser.error('profile already exists: ' + destination)
    print('Default profile destination: {}'.format(destination))
    client = read_client(args.client_secrets)
    verifier = b64url(os.urandom(48))
    state = b64url(os.urandom(24))
    code, redirect_uri = receive_code(
        client['client_id'], verifier, state, args.timeout
    )
    token = exchange_code(client, code, redirect_uri, verifier)
    path = save_profile(args.config, args.sender, client, token)
    print('Gmail OAuth profile created: ' + path)
    print('Refresh token stored privately (0600). Never commit this file.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, urllib.error.URLError) as exc:
        raise SystemExit('sendEmail-safe-google-auth: {}'.format(exc))
