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


if __name__ == '__main__':
    unittest.main()
