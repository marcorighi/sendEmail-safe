#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end offline test for the new SMTP configurator default path."""
from __future__ import print_function

import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    'sendemail_configure_test', os.path.join(ROOT, 'sendEmail-safe-configure.py')
)
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


class ConfigureDefaultTests(unittest.TestCase):
    def test_default_filename_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as home:
            prompts = [
                'smtp.example.org',
                'person+lab@example.org',
                'person+lab@example.org',
                '',
                '',
                ''
            ]
            with mock.patch.object(configure, 'effective_home', return_value=home):
                with mock.patch.object(sys, 'argv', ['sendEmail-safe-configure.py']):
                    with mock.patch.object(configure, 'ask', side_effect=prompts):
                        with mock.patch.object(configure, 'ask_bool', return_value=True):
                            with mock.patch.object(configure, 'prompt_port', return_value=587):
                                with mock.patch.object(configure, 'prompt_timeout', return_value=30.0):
                                    with mock.patch.object(configure, 'prompt_security', return_value='starttls'):
                                        with mock.patch.object(configure, 'prompt_password', return_value='test-password'):
                                            configure.main()

            directory = os.path.join(home, '.config', 'sendEmail-safe')
            path = os.path.join(
                directory,
                'person_lab_example_org_smtp_example_org.json'
            )
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(os.stat(directory).st_mode), 0o700)
            with open(path, 'r') as handle:
                profile = json.load(handle)
            self.assertEqual(profile['user'], 'person+lab@example.org')
            self.assertEqual(profile['host'], 'smtp.example.org')

    def test_second_automatic_configuration_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as home:
            path = os.path.join(home, '.config', 'sendEmail-safe',
                                'person_example_org_smtp_example_org.json')
            os.makedirs(os.path.dirname(path))
            with open(path, 'w') as handle:
                json.dump({
                    'user': 'person@example.org',
                    'from': 'person@example.org',
                    'host': 'smtp.example.org',
                    'password': 'original-secret'
                }, handle)
            os.chmod(path, 0o600)
            with mock.patch.object(configure, 'effective_home', return_value=home):
                with mock.patch.object(sys, 'argv', ['sendEmail-safe-configure.py']):
                    with mock.patch.object(configure, 'ask', side_effect=[
                        'smtp.example.org', 'person@example.org',
                        'person@example.org'
                    ]):
                        with mock.patch.object(configure, 'ask_bool', return_value=True):
                            with mock.patch.object(configure, 'prompt_port', return_value=587):
                                with self.assertRaises(SystemExit):
                                    configure.main()
            with open(path, 'r') as handle:
                self.assertEqual(json.load(handle)['password'], 'original-secret')


if __name__ == '__main__':
    unittest.main()
