#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for sendEmail-safe.py."""
from __future__ import print_function

import importlib.util
import os
import tempfile
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_module(filename, module_name):
    path = os.path.join(ROOT, filename)
    specification = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


safe = load_module('sendEmail-safe.py', 'sendemail_safe')


class SendEmailSafeTests(unittest.TestCase):
    def test_profile_name_is_resolved_inside_home(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.object(safe, 'effective_home', return_value=home):
                expected = os.path.join(
                    home,
                    '.config',
                    'sendemail-safe',
                    'brevo.json'
                )
                self.assertEqual(safe.resolve_config('brevo'), expected)

    def test_explicit_path_outside_home_is_rejected(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.object(safe, 'effective_home', return_value=home):
                with self.assertRaises(SystemExit):
                    safe.resolve_config('/tmp/outside-profile.json')

    def test_xp_is_rejected(self):
        with self.assertRaises(SystemExit):
            safe.parse([
                '--config',
                'brevo',
                '-t',
                'recipient@example.org',
                '-xp',
                'secret'
            ])

    def test_multiple_recipient_groups_are_parsed(self):
        data = safe.parse([
            '--config',
            'brevo',
            '-t',
            'one@example.org',
            'two@example.org',
            '-cc',
            'copy@example.org',
            '-u',
            'Subject',
            '-m',
            'Body'
        ])
        self.assertEqual(
            data['to'],
            ['one@example.org', 'two@example.org']
        )
        self.assertEqual(data['cc'], ['copy@example.org'])

    def test_build_message_uses_profile_sender(self):
        data = safe.parse([
            '--config',
            'brevo',
            '-t',
            'recipient@example.org',
            '-u',
            'Subject',
            '-m',
            'Body'
        ])
        config = {
            'from': 'sender@example.org',
            'user': 'smtp-login@example.org'
        }
        message, sender, recipients = safe.build_message(data, config)
        self.assertEqual(sender, 'sender@example.org')
        self.assertEqual(recipients, ['recipient@example.org'])
        self.assertEqual(message['From'], 'sender@example.org')


if __name__ == '__main__':
    unittest.main()
