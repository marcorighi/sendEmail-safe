#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline Gmail OAuth API tests: no credentials or network access required."""
from __future__ import print_function

import importlib.util
import json
import os
import stat
import tempfile
import unittest
import urllib.parse
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


safe = load('sendEmail-safe.py', 'sendemail_safe_for_google_tests')
auth = load('sendEmail-safe-google-auth.py', 'sendemail_google_auth_tests')
google = load('sendemail_safe_google.py', 'sendemail_google_tests')


class MockResponse:
    def __init__(self, content):
        self.content = json.dumps(content).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.content


class GmailTests(unittest.TestCase):
    def test_refresh_uses_secret_in_https_body_not_command_line(self):
        profile = {
            'oauth_client_id': 'client-id',
            'oauth_client_secret': 'client-secret',
            'oauth_refresh_token': 'refresh-secret'
        }
        with mock.patch.object(google.urllib.request, 'urlopen',
                               return_value=MockResponse({'access_token': 'short-lived'})) as urlopen:
            self.assertEqual(google.refresh_access_token(profile, 5), 'short-lived')
            request = urlopen.call_args[0][0]
            self.assertEqual(request.full_url, google.TOKEN_URL)
            sent = urllib.parse.parse_qs(request.data.decode('ascii'))
            self.assertEqual(sent['refresh_token'], ['refresh-secret'])

    def test_gmail_api_encodes_mime_and_requires_message_id(self):
        data = safe.parse([
            '--config', 'gmail', '-t', 'to@example.org',
            '-bcc', 'hidden@example.org', '-u', 'Subject', '-m', 'Body'
        ])
        message, sender, recipients = safe.build_message(
            data, {'from': 'sender@gmail.com'}
        )
        message['Bcc'] = ', '.join(data['bcc'])
        self.assertEqual(len(recipients), 2)
        with mock.patch.object(google, 'refresh_access_token',
                               return_value='access-token'):
            with mock.patch.object(google, 'request_json',
                                   return_value={'id': 'gmail-id'}) as request:
                self.assertEqual(google.send_message(message, {}, 10), 'gmail-id')
                url, payload, headers, timeout = request.call_args[0]
                import base64
                decoded = base64.urlsafe_b64decode(payload['raw']).decode('utf-8')
                self.assertIn('Bcc: hidden@example.org', decoded)
                self.assertEqual(url, google.SEND_URL)
                self.assertEqual(headers['Authorization'], 'Bearer access-token')
                self.assertEqual(timeout, 10)

    def test_oauth_url_uses_pkce_and_gmail_send_only(self):
        link = auth.build_auth_url(
            'client-id', 'http://127.0.0.1:9876/oauth2/callback',
            'A' * 64, 'csrf-token'
        )
        values = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)
        self.assertEqual(values['scope'], [auth.SCOPE])
        self.assertEqual(values['state'], ['csrf-token'])
        self.assertEqual(values['code_challenge_method'], ['S256'])
        self.assertNotIn('code_verifier', values)

    def test_gmail_profile_is_private_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.object(auth.profiles, 'effective_home',
                                   return_value=home):
                client = {'client_id': 'id', 'client_secret': 'public-client-value'}
                path = auth.save_profile(
                    'gmail-test', 'test@gmail.com', client, 'refresh-token'
                )
                self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
                with open(path, 'r') as handle:
                    profile = json.load(handle)
                self.assertEqual(profile['provider'], 'gmail_api')
                with self.assertRaises(ValueError):
                    auth.save_profile('gmail-test', 'test@gmail.com',
                                      client, 'replacement-token')

    def test_gmail_profile_loads_without_smtp_password(self):
        with tempfile.TemporaryDirectory() as home:
            folder = os.path.join(home, '.config', 'sendemail-safe')
            os.makedirs(folder)
            path = os.path.join(folder, 'gmail.json')
            with open(path, 'w') as handle:
                json.dump({
                    'provider': 'gmail_api',
                    'from': 'sender@gmail.com',
                    'oauth_client_id': 'id',
                    'oauth_refresh_token': 'refresh'
                }, handle)
            os.chmod(path, 0o600)
            profile = safe.load_config(path)
            self.assertEqual(profile['provider'], 'gmail_api')
            self.assertEqual(profile['timeout'], 30.0)


    def test_client_secrets_default_per_account_then_shared(self):
        with tempfile.TemporaryDirectory() as home:
            root = os.path.join(home, '.config', 'sendEmail-safe')
            directory = os.path.join(root, 'secrets')
            os.makedirs(root, mode=0o700)
            os.makedirs(directory, mode=0o700)
            account, shared = auth.client_secrets_candidates(
                'student+test@gmail.com', home=home
            )
            self.assertEqual(os.path.basename(account),
                             'student_test_gmail_com_gmail_googleapis_com_secrets.json')
            self.assertEqual(os.path.basename(shared), 'google_oauth_client.json')
            with self.assertRaises(ValueError):
                auth.resolve_client_secrets(None, 'student+test@gmail.com', home=home)
            with open(shared, 'w') as target:
                json.dump({'installed': {'client_id': 'shared-client'}}, target)
            os.chmod(shared, 0o600)
            self.assertEqual(
                auth.resolve_client_secrets(None, 'student+test@gmail.com', home=home),
                shared
            )
            with open(account, 'w') as target:
                json.dump({'installed': {'client_id': 'personal-client'}}, target)
            os.chmod(account, 0o600)
            self.assertEqual(
                auth.resolve_client_secrets(None, 'student+test@gmail.com', home=home),
                account
            )
            self.assertEqual(auth.read_client(account)['client_id'], 'personal-client')

    def test_explicit_client_secrets_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as home:
            custom = os.path.join(home, 'other-client.json')
            with open(custom, 'w') as target:
                json.dump({'installed': {'client_id': 'another-client'}}, target)
            os.chmod(custom, 0o600)
            self.assertEqual(auth.resolve_client_secrets(
                custom, 'account@gmail.com', home=home
            ), custom)
            self.assertEqual(auth.resolve_client_secrets(
                '~/other-client.json', 'account@gmail.com', home=home
            ), custom)

    def test_client_secrets_reject_world_readable_and_symlink(self):
        with tempfile.TemporaryDirectory() as home:
            source = os.path.join(home, 'google-client.json')
            with open(source, 'w') as target:
                json.dump({'installed': {'client_id': 'example'}}, target)
            os.chmod(source, 0o644)
            with self.assertRaises(ValueError):
                auth.read_client(source)
            os.chmod(source, 0o600)
            alias = os.path.join(home, 'linked-client.json')
            os.symlink(source, alias)
            with self.assertRaises(ValueError):
                auth.read_client(alias)
            self.assertEqual(auth.read_client(source)['client_id'], 'example')

    def test_client_secrets_reject_wrong_google_client_type(self):
        with tempfile.TemporaryDirectory() as home:
            source = os.path.join(home, 'web-client.json')
            with open(source, 'w') as target:
                json.dump({'web': {'client_id': 'example'}}, target)
            os.chmod(source, 0o600)
            with self.assertRaises(ValueError):
                auth.read_client(source)


    def test_default_client_rejects_public_secrets_directory(self):
        with tempfile.TemporaryDirectory() as home:
            root = os.path.join(home, '.config', 'sendEmail-safe')
            directory = os.path.join(root, 'secrets')
            os.makedirs(directory, mode=0o700)
            shared = os.path.join(directory, 'google_oauth_client.json')
            with open(shared, 'w') as out:
                json.dump({'installed': {'client_id': 'id'}}, out)
            os.chmod(shared, 0o600)
            os.chmod(directory, 0o755)
            with self.assertRaises(ValueError):
                auth.resolve_client_secrets(
                    None, 'test@gmail.com', home=home
                )
            os.chmod(directory, 0o700)
            os.chmod(root, 0o755)
            with self.assertRaises(ValueError):
                auth.resolve_client_secrets(
                    None, 'test@gmail.com', home=home
                )
            os.chmod(root, 0o700)
            self.assertEqual(
                auth.resolve_client_secrets(
                    None, 'test@gmail.com', home=home
                ), shared
            )


if __name__ == '__main__':
    unittest.main()
